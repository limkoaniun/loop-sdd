#!/usr/bin/env python3
"""Remaining-quota readings for Claude and Codex, and seat routing. Usage:
  quota.py read [--claude-cache PATH] [--codex-sessions DIR] [--now EPOCH]
  quota.py choose --readings FILE --config loop.json --seat NAME [--override FILE] [--now EPOCH]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

WINDOWS = {300: "five_hour", 10080: "seven_day"}


def as_int(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return int(value)


def safely(reader, *args):
    try:
        return reader(*args)
    except Exception:  # a quota source must never take the command down; null is the safe answer
        return None


def empty_reading(source: str, age: int) -> dict:
    return {"five_hour": None, "seven_day": None, "age_seconds": age, "source": source,
            "resets_at": {"five_hour": None, "seven_day": None}}


def read_claude(path: Path, now: float) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        limits = data["rate_limits"]
        written = float(data["written_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    reading = empty_reading("statusline-cache", max(0, int(now - written)))
    for key in ("five_hour", "seven_day"):
        window = limits.get(key) or {}
        if isinstance(window.get("used_percentage"), (int, float)):
            reading[key] = float(window["used_percentage"])
            reading["resets_at"][key] = as_int(window.get("resets_at"))
    return reading


def newest_rollout(sessions: Path) -> Path | None:
    files = [p for p in sessions.glob("*/*/*/rollout-*.jsonl") if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def read_codex(sessions: Path, now: float) -> dict | None:
    rollout = newest_rollout(sessions)
    if rollout is None:
        return None
    last: dict | None = None
    stamp: float | None = None
    try:
        for line in rollout.read_bytes().decode("utf-8", errors="replace").splitlines():
            if '"rate_limits"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload", event)
            if not isinstance(payload, dict):
                continue
            info = payload.get("info")
            limits = payload.get("rate_limits")
            if not isinstance(limits, dict):
                limits = info.get("rate_limits") if isinstance(info, dict) else None
            if isinstance(limits, dict):
                last = limits
                stamp = None
                ts = event.get("timestamp")
                if isinstance(ts, str):
                    try:
                        stamp = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        stamp = None
    except OSError:
        return None
    if last is None:
        return None
    age = int(now - (stamp if stamp is not None else rollout.stat().st_mtime))
    reading = empty_reading("session-log", max(0, age))
    for window in (last.get("primary"), last.get("secondary")):
        if not isinstance(window, dict):
            continue
        key = WINDOWS.get(window.get("window_minutes"))
        if key and isinstance(window.get("used_percent"), (int, float)):
            reading[key] = float(window["used_percent"])
            reading["resets_at"][key] = as_int(window.get("resets_at"))
    return reading


def cmd_read(args) -> int:
    now = args.now if args.now is not None else time.time()
    print(json.dumps({"claude": safely(read_claude, args.claude_cache, now), "codex": safely(read_codex, args.codex_sessions, now)}))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("read")
    p.add_argument("--claude-cache", type=Path, default=Path.home() / ".claude" / "usage-cache.json")
    p.add_argument("--codex-sessions", type=Path, default=Path.home() / ".codex" / "sessions")
    p.add_argument("--now", type=float)
    args = parser.parse_args(argv)
    if args.cmd == "read":
        return cmd_read(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
