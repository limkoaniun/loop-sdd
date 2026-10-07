#!/usr/bin/env python3
"""Write commit list, stat and diff for BASE..HEAD to one file.
Usage: review_package.py BASE HEAD OUT [--repo DIR]"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or f"git {' '.join(args)} failed")
    return done.stdout


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base"); parser.add_argument("head"); parser.add_argument("out", type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        for ref in (args.base, args.head):
            git(args.repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        rng = f"{args.base}..{args.head}"
        commits = git(args.repo, "log", "--oneline", rng)
        stat = git(args.repo, "diff", "--stat", rng)
        diff = git(args.repo, "diff", "-U10", rng)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    none = "(none)\n"
    args.out.write_text(
        f"# Review package {rng}\n\n## Commits\n\n{commits or none}\n## Stat\n\n{stat or none}\n## Diff\n\n{diff or none}",
        encoding="utf-8",
    )
    count = len(commits.splitlines())
    print(json.dumps({"path": str(args.out), "commits": count, "empty": not diff.strip()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
