#!/usr/bin/env python3
"""Remaining-quota readings for Claude and Codex, and seat routing. Usage:
  quota.py read [--claude-cache PATH] [--codex-sessions DIR] [--now EPOCH]
  quota.py choose --readings FILE --config loop.json --seat NAME [--override FILE] [--seat-overrides JSON]
                  [--avoid BACKEND] [--now EPOCH]

choose: a noop config seat always returns noop (task seat_overrides are ignored).
Under policy balance, the fresh candidate under switch_at with the lower seven_day
wins; when no candidate is fresh and under switch_at the answer is backend null,
reason quota (balance never picks blind). --avoid BACKEND applies only under
balance and only when BACKEND is one of the seat's two candidates: the other
candidate wins if it is not excluded, known, and under switch_at; otherwise the
normal balance rules run (reason "avoid unmet" when the avoided side wins).
Under policy fixed --avoid is ignored and the backend is used
(blind when its quota is unknown) unless it is over switch_at or excluded, then
the fallback if known and under switch_at, else null.
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


def is_known(reading: dict | None, stale_after: float) -> bool:
    return (
        isinstance(reading, dict)
        and isinstance(reading.get("age_seconds"), (int, float))
        and reading["age_seconds"] <= stale_after
        and isinstance(reading.get("seven_day"), (int, float))
    )


def is_over(reading: dict, switch_at: float) -> bool:
    return any(isinstance(v, (int, float)) and v >= switch_at for v in (reading.get("five_hour"), reading.get("seven_day")))


def choose(readings: dict, cfg: dict, seat_name: str, override: dict, now: float, seat_overrides: dict,
           avoid: str | None = None) -> dict:
    if cfg["seats"][seat_name].get("backend") == "noop":
        return {"backend": "noop", "reason": "noop seat", "blind": False, "candidates": ["noop"]}
    seat = {**cfg["seats"][seat_name], **seat_overrides.get(seat_name, {})}
    backend, fallback = seat["backend"], seat["fallback"]
    routing = cfg["routing"]
    stale_after, switch_at = routing["stale_after_seconds"], routing["switch_at"]
    excluded = set()
    for b, entry in override.items():
        resets_at = as_int(entry.get("resets_at")) if isinstance(entry, dict) else None
        if resets_at is None or resets_at > now:
            excluded.add(b)
    candidates = [b for b in (backend, fallback) if b not in excluded]
    result = {"blind": False, "candidates": candidates}
    if routing["policy"] == "balance":
        fresh = [b for b in candidates if is_known(readings.get(b), stale_after) and not is_over(readings[b], switch_at)]
        avoiding = avoid in (backend, fallback)
        if avoiding:
            other = fallback if avoid == backend else backend
            if other in fresh:
                return {**result, "backend": other, "reason": f"balance: avoid {avoid} (cross-model review)"}
        if fresh:
            pick = min(fresh, key=lambda b: (readings[b]["seven_day"], 0 if b == backend else 1))
            prefix = "balance: avoid unmet, " if avoiding and pick == avoid else "balance: "
            return {**result, "backend": pick, "reason": f"{prefix}lower seven_day ({readings[pick]['seven_day']}%)"}
        return {**result, "backend": None, "reason": "quota"}
    if backend in candidates:
        known = is_known(readings.get(backend), stale_after)
        if not known:
            return {**result, "backend": backend, "reason": "fixed: backend, quota unknown", "blind": True}
        if not is_over(readings[backend], switch_at):
            return {**result, "backend": backend, "reason": "fixed: backend under switch_at"}
    if fallback in candidates and is_known(readings.get(fallback), stale_after) and not is_over(readings[fallback], switch_at):
        return {**result, "backend": fallback, "reason": "fixed: fallback, backend over switch_at or excluded"}
    return {**result, "backend": None, "reason": "quota"}


def cmd_choose(args) -> int:
    try:
        readings = json.loads(args.readings.read_text(encoding="utf-8"))
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
        override = json.loads(args.override.read_text(encoding="utf-8")) if args.override and args.override.exists() else {}
        seat_overrides = json.loads(args.seat_overrides) if args.seat_overrides else {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    shape_ok = (
        isinstance(readings, dict)
        and isinstance(cfg, dict)
        and isinstance(cfg.get("seats"), dict)
        and isinstance(cfg.get("routing"), dict)
        and isinstance(override, dict)
        and isinstance(seat_overrides, dict)
        and isinstance(seat_overrides.get(args.seat, {}), dict)
    )
    if not shape_ok:
        print("error: readings, config seats/routing, override and seat-overrides must be JSON objects", file=sys.stderr)
        return 2
    if args.seat not in cfg["seats"]:
        print(f"error: unknown seat {args.seat}", file=sys.stderr)
        return 2
    now = args.now if args.now is not None else time.time()
    print(json.dumps(choose(readings, cfg, args.seat, override, now, seat_overrides, args.avoid)))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("read")
    p.add_argument("--claude-cache", type=Path, default=Path.home() / ".claude" / "usage-cache.json")
    p.add_argument("--codex-sessions", type=Path, default=Path.home() / ".codex" / "sessions")
    p.add_argument("--now", type=float)
    p = sub.add_parser("choose")
    p.add_argument("--readings", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--seat", required=True)
    p.add_argument("--override", type=Path)
    p.add_argument("--seat-overrides")
    p.add_argument("--avoid")
    p.add_argument("--now", type=float)
    args = parser.parse_args(argv)
    if args.cmd == "read":
        return cmd_read(args)
    return cmd_choose(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
