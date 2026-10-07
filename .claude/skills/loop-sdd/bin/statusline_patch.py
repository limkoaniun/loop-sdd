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
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if "usage-cache.json" in text:
        print(json.dumps({"patched": False, "reason": "already patched"}))
        return 0
    lines = text.splitlines()
    index = next((i for i, line in enumerate(lines) if line.strip() == ANCHOR), None)
    if index is None:
        print(f"error: no '{ANCHOR}' line in {path}", file=sys.stderr)
        return 2
    lines.insert(index + 1, CACHE_LINE)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"patched": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
