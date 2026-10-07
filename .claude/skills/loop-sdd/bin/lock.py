#!/usr/bin/env python3
"""Exclusive lock file. Usage:
  lock.py take PATH --owner ID
  lock.py release PATH --token TOKEN
  lock.py status PATH
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return {}


def public(data: dict) -> dict:
    try:
        age = max(0, int(time.time() - float(data.get("created_at", time.time()))))
    except (TypeError, ValueError, OverflowError):
        age = 0
    return {"held": True, "owner": data.get("owner"), "age_seconds": age}


def take(path: Path, owner: str) -> int:
    token = uuid.uuid4().hex
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        current = read(path) or {}
        print(json.dumps({"taken": False, **public(current)}))
        return 3
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "token": token, "created_at": time.time()}, handle)
    print(json.dumps({"taken": True, "token": token, "owner": owner}))
    return 0


def release(path: Path, token: str) -> int:
    current = read(path)
    if current is None:
        print(json.dumps({"released": False, "reason": "no lock"}))
        return 3
    if current.get("token") != token:
        print(json.dumps({"released": False, "reason": "token mismatch", **public(current)}))
        return 3
    path.unlink()
    print(json.dumps({"released": True}))
    return 0


def status(path: Path) -> int:
    current = read(path)
    print(json.dumps({"held": False} if current is None else public(current)))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("take"); p.add_argument("path", type=Path); p.add_argument("--owner", required=True)
    p = sub.add_parser("release"); p.add_argument("path", type=Path); p.add_argument("--token", required=True)
    p = sub.add_parser("status"); p.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "take":
        return take(args.path, args.owner)
    if args.cmd == "release":
        return release(args.path, args.token)
    return status(args.path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
