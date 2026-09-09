---
name: room-writeup
description: Scaffold, fill, and index a TryHackMe / lab room writeup in this workspace. Use when the user wants to start a new room, turn raw notes (Notion, terminal logs, screenshots) into a structured writeup, or mark a room complete. Reconstructs the real attack path faithfully - never invents results.
---

# Room writeup

Turn a security lab room into a structured Markdown writeup that matches this
repo's template and index.

## When to use

- "Start a writeup for <room>" / "tao writeup cho <room>".
- "Write up what I did on <room>" from Notion notes or terminal logs.
- "Update <room>, I finished it" - fill remaining sections and set status.

## Golden rule

Document only what was actually done. Read the owner's source notes first. If a
phase (foothold, privesc) was not performed, write it as a planned **next**
section, clearly marked - do not fabricate commands, output, or flag values.

## Steps

1. **Gather the raw work.** Read the source: a Notion page (use the Notion
   search/fetch tools), pasted terminal output, or files under a room's folder.
   Note the target IP, open ports, the vulnerability, creds, and flags.

2. **Scaffold** (skip if the file already exists):

   ```bash
   python scripts/new_writeup.py "Room Name" --category <cat> --difficulty <Easy|Medium|Hard> --os <Linux|Windows> --slug <url-slug> --tags <a,b,c>
   ```

   Categories: beginner web network windows linux privesc forensics crypto
   reversing misc.

3. **Fill the body** against `templates/writeup-template.md`:
   - **Recon** - the scan command and a port table; call out what stood out.
   - **Foothold** - the vulnerability, how it was found, the exact working
     exploit, and which user the shell runs as.
   - **Privilege escalation** - the enumeration that revealed the path and the
     escalation itself.
   - **Flags** - locations only; keep live values out of tracked files.
   - **Room questions** - short answers in order.
   - **Lessons learned** - what was new, what to reuse.

4. **Set frontmatter status:** `in-progress` while working, `complete` with a
   `completed:` date when done.

5. **Rebuild the index and commit:**

   ```bash
   python scripts/build_index.py
   git add -A && git commit -m "..."
   ```

## Style

- English in files; copy-pasteable commands using `$IP`.
- Show the failure that mattered if it explains the working path.
- Cite sources for CVEs/exploits instead of pasting whole articles.
