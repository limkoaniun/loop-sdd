#!/usr/bin/env python3
"""Validate loop.json. Usage: loopcfg.py validate PATH

Optional key check_ran_marker: a non-empty regex matched against the check
output tail to tell a test failure (exit 1 + match) from a check that did not
run. Default when absent: passed|failed|error.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

BACKENDS = {"claude", "codex", "noop"}
SEATS = ("implementer", "reviewer", "re_reviewer")
LIMITS = ("max_attempts_per_task", "max_elapsed_seconds_per_tick", "no_progress_limit", "fix_rounds_max")


def positive_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0
    )


def string_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v for v in value)


def inside_workspace(entry: str) -> bool:
    p = Path(entry)
    return not p.is_absolute() and ".." not in p.parts


def validate(cfg) -> list[str]:
    errors: list[str] = []
    if not isinstance(cfg, dict):
        return ["root must be an object"]
    for key in LIMITS:
        if not positive_number(cfg.get(key)):
            errors.append(f"{key} must be a positive finite number")
    for key in ("check_command", "allowed_paths"):
        if not string_list(cfg.get(key)):
            errors.append(f"{key} must be a non-empty string list")
        elif key == "allowed_paths" and not all(inside_workspace(e) for e in cfg[key]):
            errors.append("allowed_paths entries must be relative and must not contain ..")
    if "check_ran_marker" in cfg:
        marker = cfg["check_ran_marker"]
        if not isinstance(marker, str) or not marker:
            errors.append("check_ran_marker must be a non-empty string (default passed|failed|error)")
        else:
            try:
                re.compile(marker)
            except re.error as error:
                errors.append(f"check_ran_marker is not a valid regex: {error}")
    routing = cfg.get("routing")
    if not isinstance(routing, dict):
        errors.append("routing must be an object")
    else:
        if routing.get("policy") not in ("balance", "fixed"):
            errors.append("routing.policy must be balance or fixed")
        sw = routing.get("switch_at")
        if isinstance(sw, bool) or not isinstance(sw, (int, float)) or not 1 <= sw <= 100:
            errors.append("routing.switch_at must be a number in 1..100")
        if not positive_number(routing.get("stale_after_seconds")):
            errors.append("routing.stale_after_seconds must be a positive finite number")
    seats = cfg.get("seats")
    if not isinstance(seats, dict):
        errors.append("seats must be an object")
    else:
        for name in SEATS:
            seat = seats.get(name)
            if not isinstance(seat, dict):
                errors.append(f"seats.{name} missing")
                continue
            b, f = seat.get("backend"), seat.get("fallback")
            if b not in BACKENDS or f not in BACKENDS:
                errors.append(f"seats.{name}: backend and fallback must be one of {sorted(BACKENDS)}")
                continue
            if b == "noop" or f == "noop":
                if not (b == "noop" and f == "noop"):
                    errors.append(f"seats.{name}: noop is valid only when backend and fallback are both noop")
            elif b == f:
                errors.append(f"seats.{name}: backend and fallback must differ")
            for key in ("model", "codex_model"):
                if not isinstance(seat.get(key), str) or not seat[key]:
                    errors.append(f"seats.{name}.{key} must be a non-empty string")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "validate":
        print("usage: loopcfg.py validate PATH", file=sys.stderr)
        return 2
    try:
        cfg = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: cannot read config: {error}", file=sys.stderr)
        return 2
    errors = validate(cfg)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
