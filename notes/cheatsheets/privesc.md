# Privilege escalation checklist

## Linux

```bash
id; sudo -l
find / -perm -4000 -type f 2>/dev/null      # SUID
getcap -r / 2>/dev/null                       # capabilities
cat /etc/crontab; ls -la /etc/cron.*          # cron
ss -tlnp                                       # internal services
```

- Run `linpeas.sh` and read the red/yellow lines first.
- Check every `sudo -l` entry and SUID binary against **GTFOBins**.
- Writable `/etc/passwd`, world-writable service scripts, and PATH hijacks are common.

## Windows

```powershell
whoami /priv
systeminfo
```

- Run `winPEAS.exe` and check service permissions, unquoted service paths,
  AlwaysInstallElevated, and stored credentials.
- `SeImpersonatePrivilege` -> Potato family (PrintSpoofer / GodPotato).

### Group memberships worth checking

- **docker** -> root. See [docker-group-privesc.md](docker-group-privesc.md).
- **lxd/lxc**, **disk**, **adm**, **shadow** are similarly dangerous.

## References

- GTFOBins: https://gtfobins.github.io/
- LOLBAS: https://lolbas-project.github.io/
- PEASS-ng: https://github.com/peass-ng/PEASS-ng
