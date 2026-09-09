# Enumeration cheatsheet

Set the target once so every command below is copy-pasteable:

```bash
export IP=10.10.10.10
```

## Nmap

```bash
# fast first pass, all TCP ports
nmap -p- --min-rate 5000 -oN nmap/allports.txt $IP

# scripts + versions on the ports that came back
nmap -p 22,80,445 -sC -sV -oN nmap/detail.txt $IP

# UDP top ports (slow)
sudo nmap -sU --top-ports 50 -oN nmap/udp.txt $IP
```

## HTTP

```bash
whatweb http://$IP
gobuster dir -u http://$IP -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt,html -o gobuster.txt
ffuf -u http://$IP/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt

# virtual hosts
ffuf -u http://$IP -H "Host: FUZZ.target.thm" -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -fs 0
```

## SMB

```bash
enum4linux -a $IP
smbclient -L //$IP/ -N
smbmap -H $IP
```

## DNS

```bash
dig axfr @$IP target.thm
dnsrecon -d target.thm -n $IP
```
