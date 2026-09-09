---
room: ROOM_NAME
url: https://tryhackme.com/room/ROOM_SLUG
category: CATEGORY
difficulty: DIFFICULTY
os: TARGET_OS
tags: []
status: in-progress
started: DATE_STARTED
completed:
---

# ROOM_NAME

> One-paragraph summary of what the room teaches and how it was solved.
> Write this last, after the room is finished.

| | |
|---|---|
| **Room** | [ROOM_NAME](https://tryhackme.com/room/ROOM_SLUG) |
| **Difficulty** | DIFFICULTY |
| **Target OS** | TARGET_OS |
| **Attack path** | recon -> foothold -> privesc |

---

## 1. Recon

### Port scan

```bash
export IP=10.10.10.10
nmap -sC -sV -oN nmap/initial.txt $IP
```

| Port | Service | Version | Notes |
|---|---|---|---|
| 22/tcp | ssh | | |
| 80/tcp | http | | |

**What stood out:**
-

### Service enumeration

```bash
# commands that actually mattered
```

Findings:
-

---

## 2. Foothold

**Vulnerability:** what it is, and why it exists here.

**How it was found:**

```bash
# the command or request that proved it
```

**Exploitation:**

```bash
# the working exploit, exactly as run
```

Shell obtained as `USER`.

```bash
# stabilise the shell
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

---

## 3. Privilege escalation

**Enumeration:**

```bash
# linpeas / winpeas / manual checks that found the path
```

**The weakness:** describe the misconfiguration or vuln in one or two sentences.

**Exploitation:**

```bash
# the escalation
```

Root/SYSTEM obtained.

---

## 4. Flags

| Flag | Location | Value |
|---|---|---|
| User | `/home/user/user.txt` | `REDACTED` |
| Root | `/root/root.txt` | `REDACTED` |

---

## 5. Room questions

Answers to the room's task questions, in order. Keep them short.

**Task 1 - Title**

1. Question text -> `answer`

---

## 6. Lessons learned

- What was new here.
- What cost time, and what would have found it faster.
- Which technique is worth reusing on the next box.

## 7. References

- [Title](url)
