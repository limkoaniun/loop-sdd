# loop-sdd: design

Date: 2026-10-08
Status: approved 2026-10-08; built on branch feat/loop-sdd; see Amendments at the end

## Purpose

A project-scoped Claude Code skill that runs an interval-triggered,
subagent-driven development loop with hard limits, where each seat
(implementer, reviewer, re-reviewer) can be routed to either a Claude
subagent or an OpenAI Codex thread through the `codex` MCP server, and
where routing responds to the remaining quota on each plan.

The first consumer is this repository: a small Python package with a
pytest suite, so the deterministic check is cheap and the loop can be
left running.

## What it borrows

| Source | Borrowed |
|---|---|
| grain `feature implement` (the author's own skill) | controller never writes code; implementer / reviewer / re-reviewer seats; prompt templates; ledger with `Ruling:` lines; fix-round cap; per-task artifact folder; `review-package` helper |
| loop-engineering-labs (the author's own lab) | `loop.json` limits; lock file; snapshot-and-diff scope check; no-progress fingerprint; per-run JSON records; tri-state check |
| brittanyellich/loop-board | one markdown file per task with `status` in frontmatter; human-only status transitions |
| ching-kuo/claude-codex | per-seat routing between Claude and Codex; three-value reviewer verdict |
| goharanwar/claude-codex-review | resume the reviewer's own thread for fix rounds |
| MarcEspuna/MCP-Codex-reviewer | the controller argues with findings and records why one was rejected |
| gautamkhorana.com Ralph loop budgets | only the verifier flips a task to done; empty diff after a failed attempt is no progress |
| Addy Osmani, Loop Engineering | maker and verifier are separate agents; state lives on disk; a human inbox for what the loop cannot resolve |

Deliberately left out for the first version: a git worktree per task, and
PR-based gating. Both are additive later.

## Layout

```
loop-sdd/
  .claude/skills/loop-sdd/
    SKILL.md                 entry: init | tick | status
    actions/init.md          scaffold .loop/, validate loop.json, write statusline cache hook
    actions/tick.md          one bounded run
    actions/status.md        read-only: inbox, task table, last run
    seats/implementer.md     template, backend-agnostic
    seats/reviewer.md        template, three-value verdict
    seats/re-reviewer.md     template, per-finding verdicts
    bin/lock                 take or refuse .loop/lock; prints owner on refusal
    bin/snapshot             hash tree; diff two snapshots; list out-of-scope paths
    bin/review-package       commit list + stat + diff to a file
    bin/quota                normalized quota for claude and codex, refresh on demand
  loop.json                  limits, routing, check command, allowed paths
  tasks/NNN-slug.md          one task per file
  .loop/                     gitignored runtime state
    lock
    ledger.md                append-only
    inbox.md                 append-only, human-facing
    quota-override.json      backends known exhausted, with resets_at
    runs/<tick-id>.json      one per tick
    sdd/<task-id>/           brief, report, review packages, seat handles
  src/calc/                  toy package
  tests/                     pytest suite = the deterministic check
```

## Task file

```markdown
---
id: 001
status: pending          # pending | in_progress | blocked | done
attempts: 0
no_progress: 0
seat_overrides: {}       # optional, e.g. {implementer: {backend: codex}}
verify: null             # optional extra command run after check_command
---
# Add a parser for infix expressions

<brief: what to build, acceptance criteria, files expected to change>
```

Rules:

- Filename order is execution order.
- Only the controller edits frontmatter, and only outside the snapshot
  window. `tasks/` is not in `allowed_paths`.
- `done` requires a fresh check PASS after the last commit and a reviewer
  APPROVED, in that order.
- The controller never moves a task out of `blocked` or `done`. A human
  does, by editing the frontmatter.

## loop.json

```json
{
  "check_command": ["python3", "-m", "pytest", "-q"],
  "allowed_paths": ["src/", "tests/"],
  "max_attempts_per_task": 3,
  "max_elapsed_seconds_per_tick": 600,
  "no_progress_limit": 2,
  "fix_rounds_max": 3,
  "routing": {
    "policy": "balance",
    "switch_at": 85,
    "stale_after_seconds": 3600
  },
  "seats": {
    "implementer": {"backend": "claude", "fallback": "codex", "model": "sonnet", "codex_model": "gpt-5.4"},
    "reviewer":    {"backend": "codex",  "fallback": "claude", "model": "opus",   "codex_model": "gpt-5.4"},
    "re_reviewer": {"backend": "codex",  "fallback": "claude", "model": "sonnet", "codex_model": "gpt-5.4"}
  }
}
```

Validation at the top of every tick: every limit is a positive finite
number, `switch_at` is in 1..100, `policy` is `balance` or `fixed`,
every seat names a backend and fallback in {claude, codex} that differ,
`allowed_paths` and `check_command` are non-empty string lists with no
absolute or `..` entries. Any failure is `REFUSED`, nothing changes.

## One tick

```
 1. Lock      bin/lock .loop/lock       refused if held -> REFUSED
 2. Load      loop.json, validate       invalid -> REFUSED
 3. Pick      first task pending or in_progress by filename
              none -> IDLE
 4. Budget    attempts >= max_attempts_per_task -> blocked, inbox, STOPPED
 5. Check     run check_command fresh
              UNKNOWN -> blocked, inbox, UNKNOWN
              PASS and task in_progress with an APPROVED review on record -> done, PASS
 6. Snapshot  bin/snapshot > .loop/sdd/<id>/before.txt
 7. Attempt   attempts += 1; status in_progress; write brief
              route implementer seat (section Routing); dispatch; store handle
 8. Scope     bin/snapshot after; diff
              path outside allowed_paths -> blocked, inbox, STOPPED (not reverted)
              empty diff -> no_progress += 1; >= no_progress_limit -> blocked, inbox, STOPPED
              non-empty diff -> no_progress = 0
 9. Check     run check_command fresh (plus task.verify if set)
              FAIL -> ledger, RETRY (next tick retries same task)
              UNKNOWN -> blocked, inbox, UNKNOWN
10. Review    bin/review-package BASE HEAD; route reviewer seat; dispatch
              APPROVED -> done, PASS
              FIX -> fix loop (below)
              UNKNOWN -> blocked, inbox, UNKNOWN
11. Record    ledger line; .loop/runs/<tick>.json
12. Unlock
```

Elapsed time is checked before steps 7 and 10 and before each fix round.
Over budget -> task stays `in_progress`, STOPPED with reason `elapsed`.
The next tick resumes it.

Fix loop: one round is one implementer re-dispatch (resume the same
handle) with the Critical and Important findings verbatim, then one
re-reviewer dispatch (resume the reviewer's handle) over
`FIX_BASE..HEAD`. Minor findings are parked with a `Ruling:` ledger line
and never enter the loop. At `fix_rounds_max` with findings still open:
Minor and Important may be parked with a ruling; any open Critical ->
blocked, inbox, STOPPED. The controller never fixes code itself.

One attempt per tick is the invariant that keeps the interval trigger
safe. A tick is bounded by one implementer run, one review, and at most
`fix_rounds_max` fix rounds.

## Routing

`bin/quota` prints:

```json
{
  "claude": {"five_hour": 23.5, "seven_day": 41.2, "age_seconds": 12,   "source": "statusline-cache"},
  "codex":  {"five_hour": 8.0,  "seven_day": 15.0, "age_seconds": 3400, "source": "session-log"}
}
```

Sources:

- Claude: `~/.claude/usage-cache.json`, written by the statusline script
  from the `rate_limits` object Claude Code passes it (v2.1.80+). `init`
  appends the three lines that write this file to the statusline script
  if they are missing.
- Codex: the newest `rate_limits` event in the newest
  `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. Codex names the windows
  `primary` and `secondary`; `bin/quota` maps them onto `five_hour` and
  `seven_day` by `window_minutes`. A missing window reports `null`.

Refresh on demand: if a side is older than `stale_after_seconds`,
`bin/quota` refreshes it before answering. Codex: one probe turn through
the MCP bridge ("reply OK", cheapest model, read-only sandbox). Claude: the
controller is a Claude session and every turn redraws the statusline; if
the cache is still stale the controller writes to the inbox and treats
that side as unknown rather than guessing.

Policy, applied per seat before every dispatch, among {backend, fallback}
minus anything in `quota-override.json` whose `resets_at` is in the
future:

- `balance`: the side with the lower `seven_day` used percentage.
- `fixed`: `backend`, unless it is at or above `switch_at` on either
  window, then `fallback`.
- Both sides at or above `switch_at`, or both excluded -> STOPPED with
  reason `quota`; task unchanged; next tick re-checks.
- A side with unknown quota is eligible only under `fixed` and only as
  `backend`; the ledger records that it was chosen blind.

The error is authoritative. A dispatch that fails with a rate-limit error
(Codex: `isError: true` with Codex's text; Claude: agent failure text)
writes that backend to `quota-override.json` with the last `resets_at`
seen, re-dispatches the same seat once to the other side, and counts it as
the same attempt. If that also fails -> STOPPED, reason `quota`.

After every seat returns, the controller reads `bin/quota` again and
records the before and after readings in the run record, so `switch_at`
can be tuned from observed per-seat consumption.

## Seats

Three templates. The controller fills the brackets and sends the same
text through either backend. Shared rules:

- Everything large is a file path. Nothing is pasted into a prompt.
- No seat dispatches subagents or seeks a second opinion.
- No seat edits task frontmatter.
- No "ask before starting" section; a question is a `NEEDS_CONTEXT`
  report.

Implementer. Input: brief path, allowed paths, check command, report
path, working directory. Rules: implement only the brief; tests before
code; never delete, skip, or loosen an existing test; commit on the
current branch with a conventional subject and no co-author trailer;
report anything noticed outside the brief as a concern. Output: full
report to the report file, then under 15 lines: status `DONE` |
`DONE_WITH_CONCERNS` | `BLOCKED` | `NEEDS_CONTEXT`, commits, one-line
test summary, report path.

Reviewer. Input: brief path, report path, review package path, global
constraints. Rules: read-only; judge the diff not the report; do not
re-run the suite; inspect outside the diff only for a named risk. Output:
`APPROVED` | `FIX` | `UNKNOWN`, then Critical / Important / Minor
findings with file:line. A loosened or removed test is always Critical.
`UNKNOWN` means the diff could not be judged (missing or garbled
package).

Re-reviewer. Resumes the reviewer's handle with the findings verbatim and
the fix package. Output: `ADDRESSED` | `NOT ADDRESSED` per finding, new
breakage in the fix diff, round verdict.

Backend adapter:

| | Claude | Codex |
|---|---|---|
| Dispatch | Agent tool, `model` from seat config | `mcp__codex__codex` with `prompt`, `model`, `cwd`, `sandbox` |
| Sandbox | n/a | `workspace-write` implementer; `read-only` reviewer, re-reviewer |
| Resume | SendMessage to agent id | `mcp__codex__codex-reply` with `threadId` |
| Handle | `.loop/sdd/<id>/seat-<name>.json` | same file, field `threadId` |
| Rate-limit error | agent failure text | `isError: true` with Codex's text |

## Stop conditions

Tick outcomes, exactly one per tick, in the ledger and run record:

| Outcome | Meaning | Next tick |
|---|---|---|
| `PASS` | task went to done | next task |
| `RETRY` | attempt made, check FAIL, budget left | same task |
| `IDLE` | nothing pending or in progress | same |
| `STOPPED` | a limit fired (reason below) | per reason |
| `UNKNOWN` | check or reviewer could not judge | task blocked |
| `REFUSED` | lock held or config invalid | nothing changed |

STOPPED reasons and effect on the task:

| Reason | Task |
|---|---|
| `attempts` | blocked, inbox |
| `no_progress` | blocked, inbox |
| `fix_rounds` with open Critical | blocked, inbox |
| `scope` | blocked, inbox naming the path; not reverted |
| `elapsed` | stays in_progress; next tick resumes |
| `quota` | unchanged; next tick re-checks |
| `seat` (BLOCKED, or non-quota crash) | blocked, inbox with the seat's words |

`NEEDS_CONTEXT` -> blocked with the question in the inbox. Unblock by
editing the brief and setting `status: pending`.

Inbox entry: task id, tick id, reason, the exact path / finding /
question, and what to edit to unblock.

There is no loop-level finish. When every task is done or blocked, ticks
are IDLE. The human stops `/loop`, or adds tasks.

## Run record

`.loop/runs/<tick-id>.json`:

```json
{
  "tick_id": "20261008T101500Z-3f9a1c2e",
  "task_id": "001",
  "outcome": "RETRY",
  "reason": "check FAIL after attempt",
  "attempt": 2,
  "elapsed_seconds": 212,
  "seats": [
    {"seat": "implementer", "backend": "codex", "model": "gpt-5.4", "policy": "balance",
     "quota_before": {...}, "quota_after": {...}, "status": "DONE", "handle": "..."}
  ],
  "checks": [{"when": "before", "status": "FAIL"}, {"when": "after", "status": "FAIL"}],
  "scope": {"changed": ["src/calc/parse.py", "tests/test_parse.py"], "violations": []},
  "review": null
}
```

Ledger line: `<tick-id> task 001 attempt 2 implementer=codex check=FAIL -> RETRY`.
Rulings: `Ruling: <finding> — <why> — <cost if wrong>`.

## Trigger

```
/loop 2m /loop-sdd tick
```

`init` once per project. `status` any time. Nothing is installed in
cron; stopping `/loop` stops the loop.

## Testing the skill

- `bin/*` helpers get shell tests: lock refusal, snapshot diff and scope
  listing, review package shape, quota parsing from fixture files for
  both sources including a missing window and a stale reading.
- A fixture `tasks/` set and a deliberately broken `src/calc` module give
  a first tick a real FAIL to work on.
- Dry run: `tick` with `seats.*.backend` set to a `noop` backend that
  returns a canned DONE / APPROVED, so the control flow can be exercised
  without spending either quota. `noop` is valid only when `fallback` is
  also `noop`.

## Out of scope

Worktree per task, PR gating, parallel ticks, more than two backends,
a Python controller, hooks that enforce limits in code. All are
additive on top of the ledger and run-record formats defined here.

## Amendments from the 2026-10-08 build

Recorded after implementation and review. Each supersedes the text above
where they differ.

- **Tick step order.** Frontmatter is edited before the snapshot, never
  inside the window: route the implementer seat, then `task.py set`
  (status and attempts), then take the before-snapshot and record BASE,
  then dispatch. The budget check runs after the resume checks.
- **Review state.** `.loop/sdd/<id>/review.json` holds `verdict`, `base`,
  `head`, `attempt`, `fix_round`, `fix_base`, `pending_rereview`. The
  review base is the HEAD before the task's first attempt
  (`base.txt`), so every attempt's commits are reviewed. Reviewer and
  re-reviewer replies are persisted by the controller to
  `review-<attempt>[-fix<round>]-reply.md`; the open list lives in
  `findings.md`. `fix_round` advances only after a re-review reply.
- **Empty package.** An empty review package deletes the marker and counts
  as no progress. Noop seats are exempt, and task `seat_overrides` are
  ignored when the configured seat is noop.
- **Check evidence.** Exit 1 is FAIL only when the output matches
  `check_ran_marker` (default `passed|failed|error`); otherwise UNKNOWN.
  `init` runs the check once and refuses unless it can run.
- **Routing.** Under `balance`, with no known side under `switch_at`, the
  result is `null` (quota); blind picks exist only under `fixed` as
  `backend`. Malformed override entries exclude their backend (fail
  closed). The refresh probe is skipped for an overridden backend.
- **Seat replies.** First line is an exact token (`Status: ...`,
  `Verdict: ...`); the controller matches whole tokens. A Codex
  implementer that cannot write `.git` replies
  `Commits: none (sandbox); subject: ...` and the controller commits the
  allowed paths on its behalf. After any other reply the allowed paths
  must be clean, or it is a seat failure; a dirty tree before an attempt
  is UNKNOWN.
- **Helper failures.** Any non-zero helper exit a step does not map is
  UNKNOWN with the task unchanged and the lock released.
- **Validation.** `task.py` validates `seat_overrides` (seat names,
  backends in {claude, codex}, backend ≠ fallback). `loopcfg.py`
  validates the optional `check_ran_marker` regex.
- **Helper names.** Helpers are `bin/<name>.py`; `review-package` is
  `review_package.py`. Added: `loopcfg.py`, `task.py`, `record.py`,
  `noop.py`, `statusline_patch.py`.

## Amendments from the portable build (2026-10-08, second branch)

- **Starter config.** `loopcfg.py init [DIR]` writes `loop.json` for the
  detected stack (Python, Rust, Node, Go; precedence in that order) and
  never overwrites. An unknown stack writes a `REPLACE_ME` placeholder
  that validation refuses. `init` calls it first.
- **Runner exit codes.** `check_fail_exits` (default `[1]`) lists the exit
  codes that mean "tests ran and failed"; cargo uses 101. FAIL still
  requires a `check_ran_marker` match. `check_timeout_seconds` (default
  120; 600 in the Rust starter) bounds the check in both tick and init.
- **Scope detection.** Inside a git work tree the snapshot lists files via
  `git ls-files --cached --others --exclude-standard`, so ignored build
  output (`target/`, `node_modules/`) is never a scope change. Outside git
  it walks the tree as before.
- **Cross-model review under balance.** The reviewer and re-reviewer seats
  are routed with `--avoid <implementer backend>` read from the implementer
  handle file; under `balance` the other side is chosen when known and
  under `switch_at`, otherwise normal rules apply and never a blind pick.
  Under `fixed` the pin is respected. The fix loop routes seat
  `re_reviewer`.
- **Scope unblock.** The inbox entry carries the attempt's BASE sha and
  tells the human how to revert a committed, added, or untracked change.
- **Location independence.** The action files and seat adapters refer to
  `$SKILL`, the directory containing SKILL.md. `install.sh --user`
  symlinks the skill into `~/.claude/skills`; `install.sh <project>` copies
  it, refusing to delete the source or a home skills directory.
- **Docs.** `docs/TUTORIAL.md` is the newcomer walkthrough; the README is
  the reference.
