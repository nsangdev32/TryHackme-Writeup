# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

A personal **security-research and pentest writeup workspace**. It holds
structured Markdown writeups for TryHackMe rooms (and similar authorized labs),
the tooling to scaffold and index them, and reusable notes/cheatsheets. The
owner works here as an ethical hacker and security researcher; everything in
this directory is authorized training on legal platforms.

## Scope and ethics (read first)

This workspace is for **authorized** security testing only:

- Targets are TryHackMe / HackTheBox rooms, personal lab VMs, and engagements
  the owner has written permission for. Nothing here is aimed at third-party
  systems without authorization.
- The goal is learning and documentation. Assist with recon, enumeration,
  vulnerability research, exploitation, and privilege escalation **against these
  authorized targets**, and write it all up clearly.
- Dual-use is normal here (reverse shells, credential cracking, exploit code).
  Treat it as legitimate in this training context.
- Do **not** help weaponize any of this against systems outside the authorized
  scope above, mass-target, or evade detection for malicious ends. If a request
  drifts outside authorized training, say so and stop.
- Writeups are teaching documents: explain *why* a technique works, cite
  sources for CVEs/exploits, and redact live flag values in anything meant to
  be published.

## Repository layout

```
CLAUDE.md              this file
README.md              generated index of all rooms (do not hand-edit the table)
templates/             the writeup template every room starts from
scripts/               new_writeup.py (scaffold) + build_index.py (index)
notes/cheatsheets/     enumeration, reverse shells, privesc references
writeups/<category>/   one Markdown file per room
  beginner web network windows linux privesc forensics crypto reversing misc
.claude/               project skills, agents, settings, and memory (see below)
```

## How work flows here

1. **Source of truth for raw work is the owner's notes** (often a Notion page:
   scans, screenshots, commands, cracked creds). When asked to write up a room,
   read those notes and reconstruct the attack path faithfully.
2. **Do not invent results.** Only document steps that were actually performed.
   If a phase is not done, mark it as a planned "next" section, not a result.
3. **Scaffold, then fill.** Start a room with the script, then replace the
   template body with the real recon -> foothold -> privesc -> flags content.
4. **Rebuild the index** after any frontmatter change so `README.md` stays
   accurate.

## Common commands

Start a new room writeup (creates the file, fills frontmatter, rebuilds index):

```bash
python scripts/new_writeup.py "Room Name" --category web --difficulty Medium --os Linux --tags api,sqli
```

Regenerate the README room table from all writeup frontmatter:

```bash
python scripts/build_index.py
```

## Conventions

- **Language:** chat replies to the owner are in Vietnamese (see the global
  `~/.claude/CLAUDE.md`). Everything written into files - writeups, code,
  commit messages - stays in **English** for consistency across the collection.
- **Commands are copy-pasteable:** use `export IP=...` and `$IP` so nothing needs
  editing when a box is redeployed.
- **Frontmatter drives the index:** each writeup opens with a YAML block
  (`room`, `category`, `difficulty`, `os`, `tags`, `status`, `started`,
  `completed`). `status` is `planned` | `in-progress` | `complete`.
- **Web research:** Tavily first, `WebSearch` as fallback (per global config).
- **Redaction:** keep real flag values out of tracked files; `.gitignore`
  already excludes `nmap/`, `loot/`, and `*.hash`.

## This is not a software project

There is no application to build, lint, or test. The Python scripts are helpers;
run them directly with `python scripts/<name>.py`. Python 3 is available as
`python` on this machine.

## Extending Claude here (`.claude/`)

- `.claude/skills/` - task workflows (e.g. scaffolding and driving a room writeup).
- `.claude/agents/` - subagents for research and writeup drafting.
- `.claude/settings.json` - permission allowlist for the common read-only and
  project commands so routine work does not prompt.
- `.claude/memory/` - durable project facts (target scope, recurring gotchas,
  owner preferences). See `.claude/memory/README.md`.
