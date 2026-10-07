#!/usr/bin/env python3
"""Validate or generate loop.json. Usage: loopcfg.py validate PATH | loopcfg.py init [DIR]

Optional key check_ran_marker: a non-empty regex matched against the check
output tail to tell a test failure (exit 1 + match) from a check that did not
run. Default when absent: passed|failed|error.

Optional key check_timeout_seconds: a positive finite number of seconds the
check may run before it counts as not run. Default when absent: 120. The Rust
starter sets 600; the other starters omit it.
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

STACKS = (
    # name, marker files, check_command, check_ran_marker, check_fail_exits, allowed_paths
    ("python", ("pyproject.toml", "pytest.ini", "setup.cfg"), ["python3", "-m", "pytest", "-q"], "passed|failed|error", [1], ["src/", "tests/"]),
    ("rust", ("Cargo.toml",), ["cargo", "test"], "test result:", [101], ["src/", "tests/"]),
    ("node", ("package.json",), ["npm", "test"], "Tests:|passing|failing", [1], ["src/", "test/"]),
    ("go", ("go.mod",), ["go", "test", "./..."], "^ok|FAIL", [1], ["cmd/", "internal/", "pkg/"]),
)
UNKNOWN = ("unknown", (), ["REPLACE_ME"], "REPLACE_ME", [1], ["src/"])
DEFAULT_SEATS = {
    "implementer": {"backend": "claude", "fallback": "codex", "model": "sonnet", "codex_model": "gpt-5.4"},
    "reviewer": {"backend": "codex", "fallback": "claude", "model": "opus", "codex_model": "gpt-5.4"},
    "re_reviewer": {"backend": "codex", "fallback": "claude", "model": "sonnet", "codex_model": "gpt-5.4"},
}


def detect(directory: Path):
    found = [s for s in STACKS if any((directory / m).exists() for m in s[1])]
    return (found[0], [s[0] for s in found]) if found else (UNKNOWN, [])


def starter(directory: Path) -> tuple[dict, str]:
    (name, _, command, marker, fail_exits, allowed), all_found = detect(directory)
    note = f"detected {name}" + (f" (also saw: {', '.join(all_found[1:])}; python > rust > node > go)" if len(all_found) > 1 else "")
    if name == "unknown":
        note = "no stack marker found; replace check_command, check_ran_marker, check_fail_exits and allowed_paths before running"
    cfg = {
        "_detected": note,
        "check_command": command,
        "check_ran_marker": marker,
        "check_fail_exits": fail_exits,
        **({"check_timeout_seconds": 600} if name == "rust" else {}),
        "allowed_paths": allowed,
        "max_attempts_per_task": 3,
        "max_elapsed_seconds_per_tick": 600,
        "no_progress_limit": 2,
        "fix_rounds_max": 3,
        "routing": {"policy": "balance", "switch_at": 85, "stale_after_seconds": 3600},
        "seats": DEFAULT_SEATS,
    }
    return cfg, name


def cmd_init(directory: Path) -> int:
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    path = directory / "loop.json"
    if path.exists():
        print(json.dumps({"written": False, "reason": "exists", "path": str(path)}))
        return 0
    cfg, name = starter(directory)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": True, "path": str(path), "stack": name}))
    return 0


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
    if string_list(cfg.get("check_command")) and cfg["check_command"][0] == "REPLACE_ME":
        errors.append("check_command is the REPLACE_ME placeholder; edit loop.json before running")
    if "check_fail_exits" in cfg:
        fe = cfg["check_fail_exits"]
        if (
            not isinstance(fe, list) or not fe
            or any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 255 for v in fe)
            or len(set(fe)) != len(fe)
        ):
            errors.append("check_fail_exits must be a non-empty list of distinct integers in 1..255 (default [1])")
    if "check_timeout_seconds" in cfg and not positive_number(cfg["check_timeout_seconds"]):
        errors.append("check_timeout_seconds must be a positive finite number (default 120)")
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
    if len(argv) == 2 and argv[0] == "validate":
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
    if 1 <= len(argv) <= 2 and argv[0] == "init":
        return cmd_init(Path(argv[1]) if len(argv) == 2 else Path("."))
    print("usage: loopcfg.py validate PATH | loopcfg.py init [DIR]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
