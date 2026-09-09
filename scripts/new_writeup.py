"""Create a new room writeup from the template.

Usage:
    python scripts/new_writeup.py "Mr Robot CTF" --category linux --difficulty Medium
    python scripts/new_writeup.py "Blue" -c windows -d Easy --os Windows --tags smb,eternalblue
"""

import argparse
import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from thm_lib import (  # noqa: E402
    CATEGORIES,
    ROOT,
    TEMPLATE,
    WRITEUPS_DIR,
    slugify,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Scaffold a TryHackMe writeup.")
    parser.add_argument("room", help="Room name as shown on TryHackMe")
    parser.add_argument(
        "-c", "--category", default="misc", choices=CATEGORIES,
        help="Folder under writeups/ (default: misc)",
    )
    parser.add_argument("-d", "--difficulty", default="Easy", help="Info/Easy/Medium/Hard/Insane")
    parser.add_argument("--os", dest="target_os", default="Linux", help="Target OS")
    parser.add_argument("--slug", help="Room slug in the URL (default: derived from the name)")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing file")
    return parser.parse_args()


def main():
    args = parse_args()
    slug = args.slug or slugify(args.room)
    dest_dir = os.path.join(WRITEUPS_DIR, args.category)
    dest = os.path.join(dest_dir, slug + ".md")

    if os.path.exists(dest) and not args.force:
        sys.exit("Already exists: {p} (use --force to overwrite)".format(p=dest))

    with open(TEMPLATE, encoding="utf-8") as handle:
        body = handle.read()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    today = datetime.date.today().isoformat()

    for needle, value in (
        ("ROOM_SLUG", slug),
        ("ROOM_NAME", args.room),
        ("CATEGORY", args.category),
        ("DIFFICULTY", args.difficulty),
        ("DATE_STARTED", today),
        ("tags: []", "tags: [{t}]".format(t=", ".join(tags))),
        ("TARGET_OS", args.target_os),
    ):
        body = body.replace(needle, value)

    os.makedirs(dest_dir, exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)

    rel = os.path.relpath(dest, ROOT)
    print("Created {p}".format(p=rel))

    subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "build_index.py")],
        check=False,
    )


if __name__ == "__main__":
    main()
