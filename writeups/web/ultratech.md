---
room: UltraTech
url: https://tryhackme.com/room/ultratech1
category: web
difficulty: Medium
os: Linux
tags: [nmap, ftp, nodejs, api, ssh]
status: in-progress
started: 2026-09-09
completed:
---

# UltraTech

> Progress so far: recon complete. The host exposes FTP, SSH, a Node.js/Express
> API on 8081, and an Apache web app on 31331. Foothold and privesc are not done
> yet - the sections below marked "next" are the plan, not results.

| | |
|---|---|
| **Room** | [UltraTech](https://tryhackme.com/room/ultratech1) |
| **Difficulty** | Medium |
| **Target OS** | Linux (Ubuntu) |
| **Attack path** | recon (done) -> API/web enum -> foothold -> privesc |

---

## 1. Recon

### Port scan

Full TCP scan with service detection:

```bash
export IP=10.49.172.131
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

| Port | Service | Version | Notes |
|---|---|---|---|
| 21/tcp | ftp | vsftpd 3.0.5 | check for anonymous login |
| 22/tcp | ssh | OpenSSH 8.2p1 (Ubuntu 4ubuntu0.13) | likely the final login vector |
| 8081/tcp | http | Node.js Express framework | REST API, CORS allows PUT/DELETE/PATCH |
| 31331/tcp | http | Apache httpd 2.4.41 (Ubuntu) | main site: "UltraTech - The best of technology" |

Raw output:

```
PORT      STATE SERVICE VERSION
21/tcp    open  ftp     vsftpd 3.0.5
22/tcp    open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.13 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   3072 3b:2f:11:1f:fc:4c:c7:9f:6f:b9:37:49:de:26:cd:87 (RSA)
|   256 13:3e:36:e2:47:fd:60:a0:48:ff:0f:d7:2d:d5:5f:c9 (ECDSA)
|   256 7f:21:06:30:c6:3e:61:06:9f:04:23:1b:d1:82:23:c8 (ED25519)
8081/tcp  open  http    Node.js Express framework
|_http-cors: HEAD GET POST PUT DELETE PATCH
|_http-title: Site doesn't have a title (text/html; charset=utf-8).
31331/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
|_http-server-header: Apache/2.4.41 (Ubuntu)
|_http-title: UltraTech - The best of technology (AI, FinTech, Big Data)
```

**What stood out:**
- Two web services. The Apache site on **31331** is the public front end; the
  Node.js API on **8081** is unusual and the more promising target.
- The API on 8081 advertises **CORS with PUT/DELETE/PATCH** - a permissive API
  surface worth probing for undocumented endpoints.
- FTP (vsftpd 3.0.5) and SSH are here but need credentials; SSH is the likely
  end goal once creds are found.

---

## 2. Web / API enumeration  _(next)_

Plan, not yet executed:

```bash
# main site
whatweb http://$IP:31331
gobuster dir -u http://$IP:31331 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt,html

# node API on 8081 - look for endpoints
curl -s http://$IP:8081/
gobuster dir -u http://$IP:8081 -w /usr/share/seclists/Discovery/Web-Content/common.txt
```

To capture as results:
- Endpoints exposed by the 8081 API and what each returns.
- Any JS on the 31331 site that references the API base URL or hidden paths.

---

## 3. Foothold  _(next)_

To fill in once achieved:
- The vulnerability that yields credentials or code execution.
- The exact request/command that worked.
- Which user the first shell runs as.

---

## 4. Privilege escalation  _(next)_

To fill in once achieved:
- Enumeration output that revealed the path (`sudo -l`, SUID, group membership).
- The escalation to root.

---

## 5. Flags  _(next)_

| Flag | Location | Value |
|---|---|---|
| User | | pending |
| Root | | pending |

---

## 6. Room questions  _(next)_

Answer the room's tasks here in order as they are solved.

---

## 7. Lessons learned  _(fill in at the end)_

## 8. References

- vsftpd: https://security.appspot.com/vsftpd.html
- Express / Node.js API enumeration notes: see `notes/cheatsheets/enumeration.md`
