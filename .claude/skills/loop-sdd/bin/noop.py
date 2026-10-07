#!/usr/bin/env python3
"""Canned seat responses for dry runs. Usage:
  noop.py implementer --report PATH
  noop.py reviewer
  noop.py re-reviewer
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="seat", required=True)
    p = sub.add_parser("implementer"); p.add_argument("--report", type=Path, required=True)
    sub.add_parser("reviewer"); sub.add_parser("re-reviewer")
    args = parser.parse_args(argv)
    if args.seat == "implementer":
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("# noop implementer report\n\nNo code was changed. This is a dry run.\n", encoding="utf-8")
        print(f"Status: DONE\nCommits: none (noop)\nTests: not run (noop)\nReport: {args.report}")
    elif args.seat == "reviewer":
        print("Verdict: APPROVED\n\n### Findings\n\nNone (noop reviewer).")
    else:
        print("Verdict: ADDRESSED\n\nAll findings addressed (noop re-reviewer).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
