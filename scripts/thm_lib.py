"""Shared helpers for the TryHackMe writeup collection."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITEUPS_DIR = os.path.join(ROOT, "writeups")
TEMPLATE = os.path.join(ROOT, "templates", "writeup-template.md")
README = os.path.join(ROOT, "README.md")

CATEGORIES = [
    "beginner",
    "web",
    "network",
    "windows",
    "linux",
    "privesc",
    "forensics",
    "crypto",
    "reversing",
    "misc",
]

DIFFICULTY_ORDER = {"info": 0, "easy": 1, "medium": 2, "hard": 3, "insane": 4}
STATUS_ICON = {"complete": "done", "in-progress": "wip", "planned": "todo"}


def slugify(text):
    """Turn a room name into a filename-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "room"


def parse_frontmatter(path):
    """Read YAML-ish frontmatter from a markdown file.

    Supports `key: value` and `key: [a, b]` only, which is all the
    template uses. Returns {} when the file has no frontmatter block.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    if not text.startswith("---"):
        return {}

    end = text.find("\n---", 3)
    if end == -1:
        return {}

    data = {}
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [p.strip() for p in inner.split(",") if p.strip()]
        else:
            data[key] = value
    return data


def iter_writeups():
    """Yield (relative_path, frontmatter) for every writeup on disk."""
    for dirpath, _, filenames in os.walk(WRITEUPS_DIR):
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            yield rel, parse_frontmatter(full)
