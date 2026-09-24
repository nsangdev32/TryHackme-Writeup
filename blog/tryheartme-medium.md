# TryHackMe: TryHeartMe — Forging an Admin JWT to Buy the Hidden Flag

*A walkthrough of the "TryHeartMe" web challenge from TryHackMe's Love at First
Breach 2026 event. A Valentine-themed gift shop hands every user a JSON Web Token
to track their session — but the token is signed with a laughably weak secret, so
we simply re-sign our own token as `admin`, unlock the admin panel, and check out
the one product that matters: the flag.*

> The flag value is redacted. TryHeartMe is an authorized training challenge on
> TryHackMe; everything here was performed against a legal practice target.

---

## TL;DR — the whole chain

Web app on port 5000 (a Valentine shop) → register a normal account → session is
tracked by a **JWT cookie** carrying `"role": "user"` → decode it and notice it is
**HS256 signed with the guessable secret `secret`** → re-sign a modified token with
`"role": "admin"` in CyberChef → swap the cookie back in and refresh → the **Admin**
panel appears → open the *ValenFlag* product and "buy" it → **flag**.

No privilege escalation on the OS, no exploit code — just a trust decision the app
should never have made: signing an authorization claim with a secret an attacker
can guess.

## The target

```bash
export IP=<target-ip>
nmap -sS -vv -p- -A $IP
```

```
22/tcp    open  ssh
5000/tcp  open  upnp        # actually the app's HTTP service (Flask/Werkzeug)
```

Only two ports. SSH is not our way in — there are no credentials yet — so the whole
challenge lives on **port 5000**. Nmap labels 5000 as `upnp` from its default
port-to-service map, but browsing to it shows a web application, not UPnP:

```bash
curl -s http://$IP:5000/ | head
```

It's a **Valentine's Day gift shop** — product listings, prices, a cart, and a
sign-up form. A shop that tracks a logged-in session is exactly the kind of app
where authorization bugs hide, so we make an account and look at *how* it remembers
who we are.

## Enumeration: register and read the session

Sign up with any throwaway email and log in. Browsing a product page, one detail
stands out — the app exposes a **`role: user`** attribute tied to the account.
Wherever an app writes down a role, the immediate question is: **who enforces it,
and can I change it?**

Open the browser DevTools → **Application → Cookies** for the site. The session
isn't an opaque random ID — it's a long, dotted, base64-looking string in three
segments:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6...<payload>....<signature>
```

Three base64url segments separated by dots is the unmistakable shape of a **JSON
Web Token (JWT)**. JWTs are a common way to carry session and authorization state,
and their vulnerabilities almost always come from *implementation* choices —
weak signing secrets, missing signature verification, or trusting attacker-editable
claims. Because a JWT here decides whether we are a user or an admin, a flaw in it
means straight-up **privilege escalation**.

## Reading the token: what the shop trusts

Copy the cookie value into [jwt.io](https://www.jwt.io/) to decode the header and
payload. The header names the algorithm; the payload is the interesting part:

```json
{
  "email": "<our-account>@example.com",
  "role": "user",
  "credits": 0,
  "iat": 1771185503,
  "theme": "valentine"
}
```

Header:

```json
{ "alg": "HS256", "typ": "JWT" }
```

Two things jump out:

1. **`role` is a claim inside the token**, and the app clearly reads it to decide
   what we can see. If we can produce a token that says `admin`, the server should
   hand us the admin view.
2. The token is signed with **HS256** — a symmetric HMAC. HS256 is only as strong
   as its secret. If the secret is short or guessable, *anyone* can mint valid
   tokens; the signature stops being proof of anything.

The only thing standing between "user" and "admin" is that signature. So the whole
attack reduces to one question: **can we guess the signing secret?**

## Forging the token: the secret is `secret`

The lazy-default secret for a throwaway app is often the literal word `secret`, so
we test it first. Take the decoded payload, change one field, and re-sign with
HS256 using `secret` as the key. [CyberChef](https://gchq.github.io/CyberChef/)
does this in a single `JWT Sign` operation:

- **Recipe:** `JWT Sign` with key `secret`, algorithm `HS256`
- **Input:** the payload with `role` flipped to `admin`

```json
{
  "email": "<our-account>@example.com",
  "role": "admin",
  "credits": 0,
  "iat": 1771185503,
  "theme": "valentine"
}
```

CyberChef spits out a freshly signed, three-segment JWT. If `secret` were the wrong
key the server would reject the signature — the fact that it doesn't is the whole
bug: the shop signs an **authorization decision** with a secret an attacker guesses
on the first try.

## Becoming admin

Back in DevTools → **Application → Cookies**, replace the session cookie value with
the forged token and **refresh the page**. The server verifies the signature (valid,
because we used its real secret), reads `"role": "admin"`, and upgrades our view:

- An **Admin** entry appears in the navigation that a normal user never sees.
- Inside it sits a special product — **ValenFlag**.

Open ValenFlag and click **Buy**. The checkout — gated only by the role we just
forged — completes, and the shop reveals the flag:

```
THM{<redacted>}
```

Flag captured. From "register a normal account" to "admin checkout" was three
moves: decode, re-sign, replace.

## Why it worked

The shop made a classic JWT mistake: it treated the token as **trusted state**
while signing it with an **untrusted-strength secret**.

- The `role` claim lives *client-side*, in a cookie the user fully controls. That's
  fine **only** if the signature is unforgeable.
- HS256's security is entirely in the HMAC key. A dictionary word like `secret`
  offers no security — it's guessed instantly (and would fall in milliseconds to a
  tool like `hashcat -m 16500` or `jwt_tool`, if it weren't already the first
  thing you'd try).
- Once the secret is known, the attacker *is* the issuer. Every "verified" token
  the server sees could have been minted by the attacker, so no claim in it —
  `role`, `credits`, anything — can be believed.

## Severity

**High.** The flaw is a remote, unauthenticated-in-practice privilege escalation:
any user who can register gets a token, and from there a trivial secret-guess grants
full admin. There's no user interaction required beyond editing your own cookie, and
the impact is complete authorization bypass over whatever the admin role controls.

## Remediation

1. **Use a strong, random signing secret.** At minimum a long, high-entropy key
   (32+ random bytes) stored in configuration/secret management — never a dictionary
   word, never committed to source. Rotate the current secret; treat `secret` as
   burned, which invalidates every token an attacker may have forged.
2. **Don't trust client-held role claims.** Derive authorization from a server-side
   session record or re-check the user's role against the database on every
   privileged action, rather than believing whatever the cookie asserts.
3. **Consider asymmetric signing (RS256/EdDSA).** With a private signing key the
   server never ships to clients, a leaked or guessed *verification* key can't be
   used to forge tokens.
4. **Enforce sensitive purchases/actions server-side** with real authorization
   checks, so flipping a claim can't unlock an admin-only product.

## Takeaways

- **A signed token is only as trustworthy as its secret.** HS256 with `secret` is
  security theater — the signature proves nothing once the key is guessable.
- **Any claim you put in a client-held token is attacker-editable** unless the
  signature is genuinely unforgeable. Put `role` where the user can't reissue it.
- **Guess the boring secret first.** Before reaching for `hashcat`, try `secret`,
  the app name, and other lazy defaults — CTFs (and, uncomfortably often, real
  apps) hand you the door.
- **Recon isn't only nmap.** The real attack surface here was a single cookie; the
  win came from *reading* the session, not scanning the host.

Thanks for reading — and happy (ethical) heartbreaking. TryHeartMe is a tidy
reminder that authentication tokens are a promise, and a promise signed with
`secret` isn't worth much.
