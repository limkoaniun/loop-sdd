#!/usr/bin/env python3
"""Idempotently add a usage-cache line to a Claude Code statusline script.
Usage: statusline_patch.py PATH"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ANCHOR = "input=$(cat)"
CACHE_LINE = """printf '%s' "$input" | jq -c '{rate_limits: .rate_limits, written_at: now}' > "$HOME/.claude/usage-cache.json" 2>/dev/null"""


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: statusline_patch.py PATH", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        text = path.read_text(encoding="utf-8", newline="")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if "usage-cache.json" in text:
        print(json.dumps({"patched": False, "reason": "already patched"}))
        return 0
    lines = text.split("\n")
    # Detect EOL type from anchor line
    eol = "\n"
    index = None
    for i, line in enumerate(lines):
        if line.rstrip("\r").strip() == ANCHOR:
            index = i
            if line.endswith("\r"):
                eol = "\r\n"
            break
    if index is None:
        print(f"error: no '{ANCHOR}' line in {path}", file=sys.stderr)
        return 2
    # Insert CACHE_LINE with appropriate line ending
    cache_line_with_eol = CACHE_LINE
    if eol == "\r\n":
        cache_line_with_eol = CACHE_LINE + "\r"
    lines.insert(index + 1, cache_line_with_eol)
    new_text = "\n".join(lines)
    path.write_text(new_text, encoding="utf-8", newline="")
    print(json.dumps({"patched": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
