"""Regenerate the room table in README.md from writeup frontmatter.

Usage: python scripts/build_index.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from thm_lib import (  # noqa: E402
    DIFFICULTY_ORDER,
    README,
    STATUS_ICON,
    iter_writeups,
)

START = "<!-- BEGIN ROOM TABLE -->"
END = "<!-- END ROOM TABLE -->"


def sort_key(entry):
    _, meta = entry
    difficulty = str(meta.get("difficulty", "")).lower()
    return (
        str(meta.get("category", "zz")),
        DIFFICULTY_ORDER.get(difficulty, 9),
        str(meta.get("room", "")).lower(),
    )


def build_table(entries):
    lines = [
        "| Room | Category | Difficulty | OS | Status | Completed |",
        "|---|---|---|---|---|---|",
    ]
    for rel, meta in entries:
        room = meta.get("room") or os.path.basename(rel)[:-3]
        status = str(meta.get("status", "planned")).lower()
        lines.append(
            "| [{room}]({rel}) | {cat} | {diff} | {os} | {status} | {done} |".format(
                room=room,
                rel=rel,
                cat=meta.get("category", "-"),
                diff=meta.get("difficulty", "-"),
                os=meta.get("os", "-"),
                status=STATUS_ICON.get(status, status),
                done=meta.get("completed") or "-",
            )
        )
    return "\n".join(lines)


def build_stats(entries):
    total = len(entries)
    done = sum(
        1 for _, m in entries if str(m.get("status", "")).lower() == "complete"
    )
    wip = sum(
        1 for _, m in entries if str(m.get("status", "")).lower() == "in-progress"
    )
    return "**{total} rooms** tracked - {done} complete, {wip} in progress.".format(
        total=total, done=done, wip=wip
    )


def main():
    entries = sorted(iter_writeups(), key=sort_key)

    if not entries:
        block = "_No writeups yet. Create one with_ `python scripts/new_writeup.py \"Room Name\"`."
    else:
        block = build_stats(entries) + "\n\n" + build_table(entries)

    with open(README, encoding="utf-8") as handle:
        readme = handle.read()

    if START not in readme or END not in readme:
        sys.exit("README.md is missing the ROOM TABLE markers.")

    head, _, rest = readme.partition(START)
    _, _, tail = rest.partition(END)
    updated = head + START + "\n\n" + block + "\n\n" + END + tail

    with open(README, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)

    print("Index rebuilt: {n} writeup(s).".format(n=len(entries)))


if __name__ == "__main__":
    main()
