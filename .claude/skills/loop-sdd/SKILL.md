---
name: loop-sdd
description: Bounded, interval-triggered development loop. One tick = one task attempt + one independent review, with seats routed to Claude or Codex by remaining quota.
argument-hint: init|tick|status
disable-model-invocation: true
---

# loop-sdd

You are the controller. You dispatch seats, run helpers, read short
replies, and keep the records. You never write or fix code in this session.

Everything that must be deterministic is a helper under
`.claude/skills/loop-sdd/bin/`. Run them with `python3`. Every helper
prints JSON on success and exits 2 on bad input or 3 when it refuses.
Trust their output over your own reading of a file.

## Task

Execute the requested action: $ARGUMENTS

Read that action's file before doing anything else, and only that one.

| Action | File | Does |
|---|---|---|
| `init` | `actions/init.md` | validate loop.json, scaffold .loop/, patch the statusline cache |
| `tick` | `actions/tick.md` | one bounded run: lock, pick, attempt, check, review, record |
| `status` | `actions/status.md` | print the inbox, the task table, and the last run |

If no action was given, list these and stop.

## Standing rules

- One attempt per tick. Never loop inside a tick to try a task again.
- Only this controller edits task frontmatter, and only through
  `bin/task.py set`. Never while a seat is running.
- The controller never moves a task out of `blocked` or `done`.
- Everything large travels as a file path. Never paste a brief, a report,
  a diff, or a plan into a prompt.
- Never dispatch two seats at once.
- Never tell a reviewer what not to flag.
- A finding is never dropped without a `record.py ruling` line.
- Stop and report rather than guess on any non-zero helper exit that a step
  does not map explicitly.
