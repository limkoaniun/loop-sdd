#!/usr/bin/env python3
"""Run records, ledger lines, inbox entries. Usage:
  record.py tick --loop-dir DIR --json FILE
  record.py inbox --loop-dir DIR --task ID --tick TID --reason R --detail TEXT --unblock TEXT
  record.py ruling --loop-dir DIR --task ID --finding F --why W --cost C
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REQUIRED = ("tick_id", "task_id", "outcome", "reason", "attempt", "seats", "checks")


def append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def ledger_line(rec: dict) -> str:
    seats = " ".join(f"{s.get('seat')}={s.get('backend')}" for s in rec["seats"] if isinstance(s, dict))
    check = next((c.get("status") for c in reversed(rec["checks"]) if isinstance(c, dict)), None) or "none"
    task = rec["task_id"] if rec["task_id"] is not None else "-"
    parts = [rec["tick_id"], "task", str(task), "attempt", str(rec["attempt"])]
    if seats:
        parts.append(seats)
    parts += [f"check={check}", "->", rec["outcome"]]
    line = " ".join(parts)
    return f"{line}: {rec['reason']}" if rec.get("reason") else line


def cmd_tick(args) -> int:
    try:
        rec = json.loads(args.json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    missing = [k for k in REQUIRED if k not in rec]
    if not isinstance(rec, dict) or missing:
        print(f"error: run record missing {', '.join(missing) or 'object'}", file=sys.stderr)
        return 2
    run_path = args.loop_dir / "runs" / f"{rec['tick_id']}.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    line = ledger_line(rec)
    append(args.loop_dir / "ledger.md", line)
    print(json.dumps({"run": str(run_path), "ledger_line": line}))
    return 0


def cmd_inbox(args) -> int:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    entry = (
        f"\n## task {args.task} — {stamp} — tick {args.tick}\n\n"
        f"- reason: {args.reason}\n- detail: {args.detail}\n- unblock: {args.unblock}\n"
    )
    path = args.loop_dir / "inbox.md"
    append(path, entry)
    print(json.dumps({"inbox": str(path)}))
    return 0


def cmd_ruling(args) -> int:
    line = f"task {args.task} Ruling: {args.finding} — {args.why} — {args.cost}"
    append(args.loop_dir / "ledger.md", line)
    print(json.dumps({"ledger_line": line}))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tick"); p.add_argument("--loop-dir", type=Path, required=True); p.add_argument("--json", type=Path, required=True)
    p = sub.add_parser("inbox"); p.add_argument("--loop-dir", type=Path, required=True)
    for name in ("--task", "--tick", "--reason", "--detail", "--unblock"):
        p.add_argument(name, required=True)
    p = sub.add_parser("ruling"); p.add_argument("--loop-dir", type=Path, required=True)
    for name in ("--task", "--finding", "--why", "--cost"):
        p.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return {"tick": cmd_tick, "inbox": cmd_inbox, "ruling": cmd_ruling}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
