# Hash cracking with hashcat (and John)

Recover plaintext from captured hashes. Workflow: **identify** the hash type ->
pick the **mode** -> run a wordlist attack -> add **rules** or masks if it fails.

## 1. Identify the hash

```bash
hashid 'f357a0c52799563c7c7b76c1e7543a32'
hash-identifier
nth --text 'HASH'        # name-that-hash, gives hashcat -m and john format
```

Quick tells: 32 hex = MD5/NTLM; 40 hex = SHA1; 64 hex = SHA256; `$1$`=md5crypt,
`$5$`=sha256crypt, `$6$`=sha512crypt, `$2a$/$2b$`=bcrypt, `$y$`=yescrypt.

## 2. Common hashcat modes

| Mode | Algorithm | Looks like |
|---|---|---|
| 0 | MD5 | 32 hex |
| 100 | SHA1 | 40 hex |
| 1400 | SHA256 | 64 hex |
| 1700 | SHA512 | 128 hex |
| 1000 | NTLM (Windows) | 32 hex |
| 3000 | LM | |
| 500 | md5crypt `$1$` | Unix, old |
| 7400 | sha256crypt `$5$` | |
| 1800 | sha512crypt `$6$` | modern `/etc/shadow` |
| 3200 | bcrypt `$2*$` | slow |
| 5600 | NetNTLMv2 | Responder capture |
| 13100 | Kerberoast (TGS) | `$krb5tgs$` |
| 18200 | AS-REP roast | `$krb5asrep$` |
| 22000 | WPA/WPA2 | hccapx/pmkid |
| 1600 | Apache `$apr1$` | .htpasswd |
| 900 | MD4 | |

Full list: `hashcat --help | grep -i <algo>` or the wiki.

## 3. Crack

```bash
# straight wordlist (attack mode -a 0)
hashcat -m 0 -a 0 hash.txt /usr/share/wordlists/rockyou.txt

# with rules (hugely improves hit rate)
hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
hashcat -m 1800 hash.txt rockyou.txt -r /usr/share/hashcat/rules/rockyou-30000.rule

# show already-cracked results (from the potfile)
hashcat -m 0 hash.txt --show

# mask / brute force (-a 3): ?l lower ?u upper ?d digit ?s special ?a all
hashcat -m 0 -a 3 hash.txt '?l?l?l?l?l?d?d'      # 5 letters + 2 digits
hashcat -m 0 -a 3 hash.txt -i --increment-min 4 --increment-max 8 '?a?a?a?a?a?a?a?a'

# combinator / hybrid
hashcat -m 0 -a 6 hash.txt rockyou.txt '?d?d?d'  # word + 3 digits appended
```

Useful flags: `-O` (optimised kernel, caps password length), `-w 3` (workload),
`--username` (strip `user:hash` format), `--force` (ignore warnings in VMs).

## 4. Cracking Linux /etc/shadow

```bash
# combine passwd + shadow into john format, then crack the hash directly
unshadow /etc/passwd /etc/shadow > unshadowed.txt
# grab just the $6$... field for hashcat -m 1800, or feed unshadowed.txt to john
```

## 5. John the Ripper (quick equivalents)

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --format=raw-md5 hash.txt
john --show hash.txt
# *2john helpers turn files into crackable hashes:
ssh2john id_rsa > id_rsa.hash        # then john/hashcat -m 22921 (RSA) or 22911
zip2john secret.zip > zip.hash
```

## Notes

- `rockyou.txt` lives at `/usr/share/wordlists/rockyou.txt` on Kali (gunzip it
  once). It cracks most CTF hashes.
- Fast unsalted hashes (MD5/NTLM/SHA1) fall to wordlist+rules in seconds. Slow
  salted ones (bcrypt, sha512crypt) need a good wordlist and patience.
- The blank NTLM `31d6cfe0d16ae931b73c59d7e0c089c0` = empty password - skip it.
- Seen on UltraTech: `hashcat -m 0 hash.txt rockyou.txt` cracked the MD5 to
  `n100906` instantly.

## References

- hashcat example hashes / modes: https://hashcat.net/wiki/doku.php?id=example_hashes
- hashcat rule-based attack: https://hashcat.net/wiki/doku.php?id=rule_based_attack
- John the Ripper: https://www.openwall.com/john/
