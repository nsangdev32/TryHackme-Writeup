# TryHackMe: Signed Messages — Predictable RSA Seeds Break Every Heart (and Signature)

*A walkthrough of the "Signed Messages" web challenge from TryHackMe's Love at First
Breach 2026 event. "LoveNote" lets you log in with just a username, then signs your
messages with a per-user RSA key. The catch: a debug page reveals that every user's
private key is derived deterministically from their username — so we regenerate the
admin's private key from scratch, forge a signature, and capture the flag. No
factoring required.*

> The flag is redacted. This is an authorized training challenge on TryHackMe;
> everything here was performed against a legal practice target.

---

## TL;DR — the whole chain

Web app "LoveNote" on port 5000 → **login needs only a username** (broken auth), so
log in as `admin` → the Flask session cookie decodes to `{"username":"admin"}` →
authenticated content-scan reveals a **`/debug`** route → `/debug` leaks the
**deterministic key-generation algorithm**: the RSA private key is seeded entirely
by the username (`{username}_lovenote_2026_valentine`) → **regenerate admin's private
key locally**, sign the required message with **RSA-PSS**, submit the forged
signature → **flag**.

The whole crypto theme is a distraction: the keys aren't strong, they're *predictable*.

## The target

```bash
export IP=<target-ip>
```

LoveNote is a Flask app on port 5000 that lets users send cryptographically "signed"
love notes. A heavy PKI/signature theme usually means the intended bug is in *how*
the crypto is set up, not in breaking the math head-on.

## Broken authentication: login with a username, nothing else

The first oddity is the login itself. The app states:

> "LoveNote uses your username to load your cryptographic keys."

There's **no password field** — you authenticate by naming yourself. So we just log
in as `admin`. Flask's default session cookie is signed but **not encrypted**, and
base64-decoding it confirms the server trusts exactly what we typed:

```
session=eyJ1c2VybmFtZSI6ImFkbWluIn0.<sig>   ->   {"username":"admin"}
```

We're admin. But the visible messages are seed data — no flag yet. The real
objective clearly lives in the signature machinery, so we enumerate what the
authenticated app exposes.

## Enumeration: an authenticated content scan finds `/debug`

Running gobuster **with our admin session cookie** surfaces routes a logged-out
scan would miss:

```bash
gobuster dir -u http://$IP:5000/ -w /usr/share/wordlists/dirb/big.txt -t 100 \
  -c "session=<admin-session-cookie>"
```

```
about        (200)
compose      (200)
dashboard    (200)
debug        (200)   <-- interesting
login        (200)
logout       (302)
messages     (200)
register     (200)
verify       (200)
```

A **`/debug`** endpoint on a crypto app is exactly where secrets leak.

## The vulnerability: deterministic key generation

`/debug` discloses how LoveNote builds each user's RSA keypair — and it's fully
deterministic from the username:

```
seed = f"{username}_lovenote_2026_valentine"
p    = next_prime( int(SHA256(seed))        )
q    = next_prime( int(SHA256(seed + b"pki")) )
n    = p * q
e    = 65537
```

This is the whole game. RSA's security rests on the private key being *secret and
unpredictable*. Here the private key is a pure function of the **public username**
and a **hardcoded constant** (`_lovenote_2026_valentine`). Anyone who knows a
username can recompute that user's `p`, `q`, and therefore the private exponent `d`
— no factoring, no side channel. (The keys are also tiny — ~509-bit `n` from the
exported PEMs — but we don't even need that weakness; predictability alone is fatal.)

For confirmation, the app hands out a keypair for a user we create, and OpenSSL
shows the modulus/primes line up with the formula:

```bash
openssl rsa -in key.pem -text -noout          # private: 509-bit, 2 primes
openssl rsa -pubin -in pubkey.pem -text -noout # public: same modulus, e=65537
```

## Exploitation: regenerate admin's key and forge a signature

Since the private key is deterministic, we rebuild **admin's** key locally from the
seed and sign whatever message the challenge asks us to sign. LoveNote verifies with
**RSA-PSS / SHA-256** (as its `/about` page states), so we match that padding:

```python
import hashlib, sys
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

def is_prime(n):
    if n < 2: return False
    for p in [2,3,5,7,11,13,17,19,23,29,31,37]:
        if n % p == 0: return n == p
    d, r = n-1, 0
    while d % 2 == 0: d //= 2; r += 1
    for a in [2,3,5,7,11,13,17,19,23,29,31,37]:
        x = pow(a, d, n)
        if x in (1, n-1): continue
        for _ in range(r-1):
            x = x*x % n
            if x == n-1: break
        else: return False
    return True

def next_prime(x):
    if x % 2 == 0: x += 1
    while not is_prime(x): x += 2
    return x

def priv_for(username, e=65537):
    seed = f"{username}_lovenote_2026_valentine".encode()
    p = next_prime(int.from_bytes(hashlib.sha256(seed).digest(), 'big'))
    q = next_prime(int.from_bytes(hashlib.sha256(seed + b"pki").digest(), 'big'))
    d = pow(e, -1, (p-1)*(q-1))
    nums = rsa.RSAPrivateNumbers(p, q, d, d % (p-1), d % (q-1), pow(q, -1, p),
                                 rsa.RSAPublicNumbers(e, p*q))
    return nums.private_key()

user, msg = sys.argv[1], sys.argv[2].encode()
sig = priv_for(user).sign(
    msg,
    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
    hashes.SHA256(),
)
print(sig.hex())
```

```bash
python3 forge.py admin "test"
# -> 011992d1c599...<signature hex>
```

Submitting the forged signature for `admin` through the app's verify/compose flow
passes verification — the server checks it against admin's public key, which is the
mate of the private key we just reconstructed. LoveNote accepts us as the genuine,
key-holding `admin`, and the flag drops:

```
THM{<redacted>}
```

## Why it worked

- **Predictable secrets aren't secrets.** Deriving a private key from a public
  identifier plus a constant means the "private" key is public knowledge in disguise.
- **Username-only login is no authentication.** Trusting a name with no proof of
  ownership is a straight identity bypass; here it also loads the victim's key
  context for you.
- **Debug endpoints leak the crown jewels.** A `/debug` route describing the key
  algorithm turned a "hard" crypto challenge into a copy-the-formula exercise.

## Severity

**Critical.** Any user (or anonymous visitor who can register/login by name) can
impersonate **any** user, including `admin`, and forge valid signatures for arbitrary
messages — a complete break of both authentication and message integrity.

## Recommended fix

1. **Generate keys from a cryptographically secure random source**, never from a
   username or any guessable seed, and use modern key sizes (RSA ≥ 2048-bit or move
   to Ed25519). Store private keys server-side, protected, and never expose them.
2. **Require real authentication** (password/passkey/MFA) — a username is an
   identifier, not a credential.
3. **Remove debug/diagnostic routes from production** and never disclose key-material
   generation logic.

## Takeaways

- **The scary-looking crypto is often a red herring.** Don't reach for factoring or
  lattice attacks before checking *how the keys were made*. Predictability beats
  brute force.
- **Signed ≠ trustworthy.** A signature only means something if the signing key is
  genuinely secret. Reproduce the key and you reproduce the signer.
- **Authenticated enumeration matters.** `/debug` only showed up once we scanned
  with a valid session — always re-enumerate after gaining access.

Thanks for reading. "Signed Messages" earns its event tagline: predictable seeds
really do break hearts — and every signature that depends on them.
