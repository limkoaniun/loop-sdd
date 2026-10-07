#!/usr/bin/env python3
"""Task file frontmatter. Usage:
  task.py pick DIR
  task.py show PATH
  task.py set PATH key=value [key=value ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STATUSES = ("pending", "in_progress", "blocked", "done")
KEYS = ("id", "status", "attempts", "no_progress", "seat_overrides", "verify")


class TaskError(Exception):
    pass


def parse_value(key: str, raw: str):
    raw = raw.strip()
    if key in ("seat_overrides", "verify"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise TaskError(f"{key} must be inline JSON: {error}") from error
    if key in ("attempts", "no_progress"):
        if not raw.isdigit():
            raise TaskError(f"{key} must be a non-negative integer, got {raw}")
        return int(raw)
    if key == "status":
        if raw not in STATUSES:
            raise TaskError(f"status must be one of {STATUSES}, got {raw}")
        return raw
    if key == "id":
        return raw.strip('"')
    raise TaskError(f"unknown key {key}")


def validate(fm: dict) -> None:
    if not isinstance(fm.get("seat_overrides"), dict):
        raise TaskError("seat_overrides must be a JSON object")
    v = fm.get("verify")
    if v is not None and not (isinstance(v, list) and all(isinstance(s, str) for s in v)):
        raise TaskError("verify must be null or a JSON string list")


def load(path: Path) -> tuple[dict, str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise TaskError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise TaskError("unterminated frontmatter")
    fm: dict = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, raw = line.partition(":")
        if not sep:
            raise TaskError(f"bad frontmatter line: {line}")
        fm[key.strip()] = parse_value(key.strip(), raw)
    for key in KEYS:
        if key not in fm:
            raise TaskError(f"missing key {key}")
    validate(fm)
    body = text[end + 5:]
    title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), "")
    return fm, body, title


def dump(fm: dict, body: str) -> str:
    lines = ["---"]
    for key in KEYS:
        value = fm[key]
        if key == "id":
            lines.append(f'id: "{value}"')
        elif key in ("seat_overrides", "verify"):
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def summary(path: Path, fm: dict, title: str) -> dict:
    return {"path": str(path), "title": title, **{k: fm[k] for k in KEYS}}


def pick(directory: Path) -> int:
    if not directory.is_dir():
        raise TaskError(f"not a directory: {directory}")

    # Load and validate every file first
    files: list[tuple[Path, dict, str]] = []
    for path in sorted(directory.glob("*.md")):
        try:
            fm, _, title = load(path)
            files.append((path, fm, title))
        except TaskError as error:
            print(f"error: {path.name}: {error}", file=sys.stderr)
            return 2

    # Pick the first pending or in_progress
    for path, fm, title in files:
        if fm["status"] in ("pending", "in_progress"):
            print(json.dumps(summary(path, fm, title)))
            return 0

    print("null")
    return 0


def show(path: Path) -> int:
    fm, _, title = load(path)
    print(json.dumps(summary(path, fm, title)))
    return 0


def set_values(path: Path, pairs: list[str]) -> int:
    fm, body, title = load(path)
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or key not in KEYS:
            raise TaskError(f"expected key=value with a known key, got {pair}")
        fm[key] = parse_value(key, raw)
    validate(fm)
    path.write_text(dump(fm, body), encoding="utf-8")
    print(json.dumps(summary(path, fm, title)))
    return 0


def main(argv: list[str]) -> int:
    try:
        if len(argv) >= 2 and argv[0] == "pick":
            return pick(Path(argv[1]))
        if len(argv) == 2 and argv[0] == "show":
            return show(Path(argv[1]))
        if len(argv) >= 3 and argv[0] == "set":
            return set_values(Path(argv[1]), argv[2:])
    except (TaskError, OSError) as error:
        print(f"error: {argv[1] if len(argv) > 1 else ''}: {error}", file=sys.stderr)
        return 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
