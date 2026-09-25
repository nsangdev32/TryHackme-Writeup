# TryHackMe: Hidden Deep Into my Heart — robots.txt Spills a Secret Vault and a Password

*A walkthrough of the "Hidden Deep Into my Heart" web challenge from TryHackMe's
Love at First Breach 2026 event. The box practically leaves the front door open:
`robots.txt` points at a hidden directory and leaks a password-shaped string, a
quick content scan turns up the admin login inside that directory, and the leaked
string logs us straight in as the administrator.*

> The flag and credentials are redacted. This is an authorized training challenge
> on TryHackMe; everything here was performed against a legal practice target.

---

## TL;DR — the whole chain

Web app on port 5000 → read **`/robots.txt`**, which discloses a hidden path
`/cupids_secret_vault/` **and** a suspicious password-shaped string → **gobuster**
the vault and find an **`administrator`** login page → reuse the leaked string as
the admin password → **authenticated as admin**, flag in the admin area.

No exploit — just enumeration and a credential the site handed us for free.

## The target

```bash
export IP=<target-ip>
```

A Valentine-themed web app on port 5000. When a challenge is called "hidden deep
into my heart," the hint is unsubtle: something is *hidden*, and the first place to
look for things a site would rather you not see is the file that literally lists
them.

## Enumeration: read `robots.txt` first

`robots.txt` is a directive for crawlers, not a security control — and developers
routinely list the exact paths they want kept private, which makes it a free map
for an attacker:

```bash
curl -s http://$IP:5000/robots.txt
```

Two things fall out of it:

1. A **`Disallow` entry for a hidden directory**, `/cupids_secret_vault/` — the
   "secret" area the challenge name teased.
2. A **stray string that looks a lot like a password** (`cupid_arrow_...`,
   redacted). On its own it means nothing, but it's the kind of value you note and
   try later against any login you find.

`robots.txt` just told us *where* to knock and, quite possibly, *what to say*.

## Finding the admin login inside the vault

The vault path doesn't render anything useful on its own, so we brute-force its
contents with **gobuster**, looking for pages and common extensions:

```bash
gobuster dir -u http://$IP:5000/cupids_secret_vault/ \
  -w /usr/share/wordlists/dirb/big.txt -t 100 -x php,txt,js,html,bak
```

```
administrator        (Status: 200) [Size: 2381]
```

There it is — an **`administrator`** endpoint returning `200`. Browsing to
`http://$IP:5000/cupids_secret_vault/administrator` shows an admin login form.

## Foothold: log in as admin with the leaked password

Now the two clues connect. We have an admin login and a password-shaped string that
`robots.txt` leaked. The obvious guess for the username on an admin panel is
`admin`, so we try the pair:

```
username: admin
password: <redacted — the string leaked in robots.txt>
```

It works. We land in the authenticated **admin** area, where the challenge flag is
displayed:

```
THM{<redacted>}
```

From an anonymous request to admin access, the only "skills" required were reading
`robots.txt`, running one directory scan, and reusing a credential the site
published itself.

## Why it worked

This challenge is a chain of small disclosure and hygiene failures, each harmless in
isolation and fatal together:

- **`robots.txt` used as a hiding place.** Listing a sensitive directory in
  `robots.txt` doesn't hide it — it advertises it. Crawlers ignore it *by request*;
  attackers read it *first*.
- **A secret stored in a public file.** A password (or anything password-shaped) in
  a client-readable file is already leaked. There's no such thing as "obscure enough."
- **A predictable admin username and reused credential.** `admin` plus a
  password that lives in plaintext on the server is a one-line break-in.

## Severity

**High.** Full administrative access with no exploitation, achievable by any
anonymous user in a couple of requests. Anything the admin role controls is exposed.

## Recommended fix

1. **Never put secrets in `robots.txt`** (or any client-served file). If a path must
   be private, protect it with real authentication and authorization — not a
   `Disallow` line.
2. **Remove the leaked password** and rotate it; treat the exposed value as burned.
   Store credentials hashed, never in flat files under the web root.
3. **Move the admin panel behind authentication that doesn't depend on obscurity**,
   and consider IP-allowlisting or MFA for administrative logins.

## Takeaways

- **`robots.txt` is recon gold.** It's the first thing to `curl` on any web target;
  it often names the exact directories the developer considered sensitive.
- **Obscurity is not security.** Hiding a path or a secret in a file the browser can
  fetch just means the attacker finds it a few seconds later.
- **Note every stray string.** A random-looking token on one page is often the
  password for a login on another — connect the clues.

Thanks for reading. "Hidden Deep Into my Heart" is a tidy reminder that the fastest
path in is often the one the target documented for you.
