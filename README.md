# TryHackMe Writeups

Personal notes and full solution walkthroughs for TryHackMe rooms. Every room gets
one markdown file with the same structure: recon, foothold, privilege escalation,
flags, task answers, and what was learned.

## Rooms

<!-- BEGIN ROOM TABLE -->

**1 rooms** tracked - 1 complete, 0 in progress.

| Room | Category | Difficulty | OS | Status | Completed |
|---|---|---|---|---|---|
| [Blue](writeups/windows/blue.md) | windows | Easy | Windows | done | 2026-09-09 |

<!-- END ROOM TABLE -->

The table above is generated. Do not edit it by hand - run `python scripts/build_index.py`.

## Starting a new room

```bash
python scripts/new_writeup.py "Mr Robot CTF" --category linux --difficulty Medium --tags wordpress,john,privesc
```

That creates `writeups/linux/mr-robot-ctf.md` from the template, fills in the
frontmatter, and rebuilds the index. Options:

| Flag | Meaning | Default |
|---|---|---|
| `-c`, `--category` | folder under `writeups/` | `misc` |
| `-d`, `--difficulty` | Info / Easy / Medium / Hard / Insane | `Easy` |
| `--os` | target operating system | `Linux` |
| `--slug` | room slug in the TryHackMe URL | derived from the name |
| `--tags` | comma-separated tags | empty |
| `--force` | overwrite an existing file | off |

## Layout

```
writeups/          one file per room, grouped by category
  beginner/  web/  network/  windows/  linux/
  privesc/   forensics/  crypto/  reversing/  misc/
templates/         the writeup template every room starts from
scripts/           new_writeup.py (scaffold) and build_index.py (index)
notes/cheatsheets/ command references reused across rooms
```

## Frontmatter

Each writeup opens with a block the index reads:

```yaml
---
room: Blue
url: https://tryhackme.com/room/blue
category: windows
difficulty: Easy
os: Windows
tags: [smb, eternalblue, hashcat]
status: complete        # planned | in-progress | complete
started: 2026-09-09
completed: 2026-09-09
---
```

Change `status` to `complete` and set `completed` when a room is finished, then
rebuild the index.

## Conventions

- **Commands are copy-pasteable.** Use `$IP` for the target address so nothing
  needs editing when the machine is redeployed.
- **Show the failures that mattered.** A path that did not work is worth a line
  if it explains why the working path was chosen.
- **Redact flags** in anything that gets published. Keep real values local only.
- **Cite sources** for exploits and CVEs rather than pasting whole articles.
