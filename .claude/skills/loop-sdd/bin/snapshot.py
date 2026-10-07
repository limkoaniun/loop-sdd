#!/usr/bin/env python3
"""Hash a tree and compare two hashes against allowed paths. Usage:
  snapshot.py take ROOT
  snapshot.py scope BEFORE AFTER --allowed P [P ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

SKIP = {".git", ".loop", "__pycache__", ".pytest_cache"}


def take(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP)
        for name in sorted(filenames):
            full = Path(dirpath) / name
            if full.is_symlink():
                continue
            rel = full.relative_to(root).as_posix()
            result[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
    return result


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def allowed(path: str, entries: list[str]) -> bool:
    for entry in entries:
        entry = entry.strip("/") if entry.endswith("/") else entry
        if path == entry or path.startswith(entry.rstrip("/") + "/"):
            return True
    return False


def scope(before_file: Path, after_file: Path, entries: list[str]) -> dict:
    before = json.loads(before_file.read_text(encoding="utf-8"))
    if not isinstance(before, dict):
        raise ValueError(f"snapshot file must be a JSON object: {before_file}")
    after = json.loads(after_file.read_text(encoding="utf-8"))
    if not isinstance(after, dict):
        raise ValueError(f"snapshot file must be a JSON object: {after_file}")
    changed = changed_paths(before, after)
    return {"changed": changed, "violations": [p for p in changed if not allowed(p, entries)]}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("take"); p.add_argument("root", type=Path)
    p = sub.add_parser("scope")
    p.add_argument("before", type=Path); p.add_argument("after", type=Path)
    p.add_argument("--allowed", nargs="+", required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "take":
            root = args.root.resolve()
            if not root.is_dir():
                print(f"error: not a directory: {root}", file=sys.stderr)
                return 2
            print(json.dumps(take(root), sort_keys=True))
        else:
            print(json.dumps(scope(args.before, args.after, args.allowed)))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
