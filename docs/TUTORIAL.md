# loop-sdd tutorial

This walks you through putting loop-sdd on a project you already have, from
install to a running loop. It assumes you have never seen this repo. The
[README](../README.md) is the reference; this file is the walkthrough. Each
section says what you type, what you should see, and what it means.

Commands that start with `/` are typed inside a Claude Code session started
in your project. Everything else is a shell command.

## 1. Install

### Before you start

You need:

- Claude Code 2.1.80 or later.
- The Codex CLI, logged in, and registered in Claude Code as the MCP server
  named `codex`. The controller dispatches Codex seats through the
  `mcp__codex__codex` tool, so the server name must be exactly `codex`.
- Python 3.11 or later, available as `python3`. Every helper runs as
  `python3 <skill>/bin/<name>.py`.
- git. The project must be a git repository. The loop reads `HEAD`, builds
  review packages from commits, and checks `git status`.
- `jq`, if you want Claude quota readings. The line `init` adds to your
  statusline script pipes through `jq`.

### What you type

From a clone of this repo, pick one of two modes:

```bash
./install.sh --user
```

This makes one symlink, `~/.claude/skills/loop-sdd`, pointing at
`.claude/skills/loop-sdd` in your clone. `/loop-sdd` then works in every
project. Because it is a symlink, pulling new commits into the clone updates
the skill everywhere. Do not move or delete the clone.

```bash
./install.sh /path/to/project
```

This copies `SKILL.md`, `actions/`, `seats/` and `bin/` into
`/path/to/project/.claude/skills/loop-sdd`. Only that project gets the skill.
The copy does not follow later changes to the clone. Re-run with `--force` to
replace it.

### What you should see

On success the script prints `linked: ...` or `copied: ...`, then a short
"Installed. Next:" list. Check the result:

```bash
ls ~/.claude/skills/loop-sdd              # after --user
ls /path/to/project/.claude/skills/loop-sdd   # after a project install
```

You should see `SKILL.md`, `actions`, `bin` and `seats` (a `--user` install
also shows `tests`, because it links the whole directory).

### When it refuses

The installer stops with exit 1 and changes nothing when:

- `--user`: `~/.claude/skills/loop-sdd` is already a symlink to somewhere
  else ("remove it first"), or exists and is not a symlink ("move it aside
  first"). If it is already linked to this clone it says `already linked`
  and exits 0.
- project mode: the target `.claude/skills/loop-sdd` already exists and you
  did not pass `--force`.
- project mode with `--force`: the target resolves to the skill source in
  this clone, or the project's `.claude/skills` resolves inside
  `~/.claude`. In the second case use `--user` instead.

A path that is not a directory exits 2. A project without a `.git`
directory only gets a warning, but the loop needs git when it runs.

## 2. Create loop.json

### What you type

Start Claude Code in your project and run:

```
/loop-sdd init
```

### What you should see

If there is no `loop.json`, init writes one for the stack it detects and
prints the `_detected` note. It never overwrites an existing `loop.json`.
Detection looks for marker files in the project root:

| Stack | Marker files | `check_command` | `check_ran_marker` | `check_fail_exits` | `allowed_paths` |
|---|---|---|---|---|---|
| python | `pyproject.toml`, `pytest.ini`, `setup.cfg` | `python3 -m pytest -q` | `passed\|failed\|error` | `[1]` | `src/`, `tests/` |
| rust | `Cargo.toml` | `cargo test` | `test result:` | `[101]` | `src/`, `tests/` |
| node | `package.json` | `npm test` | `Tests:\|passing\|failing` | `[1]` | `src/`, `test/` |
| go | `go.mod` | `go test ./...` | `^ok\|FAIL` | `[1]` | `cmd/`, `internal/`, `pkg/` |

If more than one stack matches, the first in the order python, rust, node, go
wins, and the note says what else it saw.

For a project with a `pyproject.toml`, the generated file is:

```json
{
  "_detected": "detected python",
  "check_command": [
    "python3",
    "-m",
    "pytest",
    "-q"
  ],
  "check_ran_marker": "passed|failed|error",
  "check_fail_exits": [
    1
  ],
  "allowed_paths": [
    "src/",
    "tests/"
  ],
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
    "implementer": {
      "backend": "claude",
      "fallback": "codex",
      "model": "sonnet",
      "codex_model": "gpt-5.4"
    },
    "reviewer": {
      "backend": "codex",
      "fallback": "claude",
      "model": "opus",
      "codex_model": "gpt-5.4"
    },
    "re_reviewer": {
      "backend": "codex",
      "fallback": "claude",
      "model": "sonnet",
      "codex_model": "gpt-5.4"
    }
  }
}
```

For a project with a `Cargo.toml`, only these lines differ:

```json
  "_detected": "detected rust",
  "check_command": ["cargo", "test"],
  "check_ran_marker": "test result:",
  "check_fail_exits": [101],
```

After writing the file, init validates it, runs the check command once,
creates `.loop/`, adds `.loop/` to `.gitignore`, patches your statusline
script, and prints the current quota readings. It ends with the start
command `/loop 2m /loop-sdd tick`. Do not start the loop yet.

### What to review

Open `loop.json` and check these lines before anything else.

**`check_command`.** This is how the loop decides whether the code works. It
runs before and after every attempt, in the project root, with a 120-second
timeout. If it points at the wrong interpreter or the wrong test runner,
every tick reads as `UNKNOWN` and blocks the task. For Python, `python3`
must be an interpreter that has pytest installed in the shell Claude Code
runs commands in. If it takes longer than 120 seconds, it counts as a check
that did not run.

**`check_fail_exits` and `check_ran_marker`.** Together they separate "the
tests ran and some failed" from "the tests did not run at all". A check
counts as a failure (`FAIL`) only if its exit code is in `check_fail_exits`
AND the last 20 lines of output match the regex `check_ran_marker`. Exit 0
is always `PASS`. Anything else is `UNKNOWN`. If `check_fail_exits` is
wrong (for example `[1]` on a Rust project, where `cargo test` exits 101 on
a test failure), every real test failure reads as `UNKNOWN` and the task is
blocked instead of retried. If `check_ran_marker` is too loose, a broken
environment that happens to print "error" looks like a test failure, and
the loop keeps retrying something no code change can fix.

**`allowed_paths`.** The only paths the implementer may change. After each
attempt the loop hashes the tree and compares it with the snapshot taken
before. Any changed file outside these paths blocks the task with reason
`scope`. Too narrow, and correct work is blocked. Too wide, and a seat can
change things you did not mean to hand over. Entries must be relative and
must not contain `..`. Keep `tasks/` and `loop.json` out of this list (see
section 3).

**The seats.** `implementer`, `reviewer` and `re_reviewer` each name a
`backend` and a `fallback` (`claude`, `codex`, or `noop`), a Claude `model`
and a `codex_model`. `backend` and `fallback` must differ, except that
`noop` is valid only when both are `noop`. If a model name is one your plan
cannot use, the seat fails at dispatch time and the task is blocked with
reason `seat`. The defaults put the implementer on Claude and both reviewers
on Codex, so the maker and the checker are different models.

**Limits.** `max_attempts_per_task`, `max_elapsed_seconds_per_tick`,
`no_progress_limit` and `fix_rounds_max` must be positive finite numbers.
The defaults are a reasonable start.

The `_detected` key is a note for you. Validation ignores it.

### What init refuses

Init stops, and nothing else runs, when:

- **The stack is unknown.** With no marker file, init still writes
  `loop.json`, but with `REPLACE_ME` in `check_command` and
  `check_ran_marker`. Validation refuses it with "check_command is the
  REPLACE_ME placeholder; edit loop.json before running". Fill in your real
  test command, marker, fail exits and paths, then run `/loop-sdd init`
  again.
- **The file is invalid.** Zero, negative or missing limits, an empty
  `check_command`, a `check_fail_exits` that is not a non-empty list of
  distinct integers from 1 to 255, a `check_ran_marker` that is not a valid
  regex, a `routing.switch_at` outside 1 to 100, or a bad seat. Init prints
  every error and stops.
- **The check cannot run.** Init runs `check_command` once. Unless it exits
  0, or exits with a code in `check_fail_exits` and the output tail matches
  `check_ran_marker`, init prints the exit code and tail and then "init
  refused: check command cannot run". A tick would read every result as
  `UNKNOWN`, so there is no point starting. A common cause on Python: a
  project with no tests yet. pytest exits 5 when it collects nothing, and 5
  is not in `[1]`. Add one test first.

Init is safe to re-run. Re-run it after every fix until it reports the
config valid.

## 3. Write your first task

### What you type

Create `tasks/001-<slug>.md`, for example `tasks/001-infix-tokenizer.md`:

```markdown
---
id: "001"
status: pending
attempts: 0
no_progress: 0
seat_overrides: {}
verify: null
---
# Add a tokenizer for infix expressions

Add `src/calc/tokens.py` with `tokenize(text: str) -> list[Token]` where
`Token` is a dataclass with `kind` in `{"number", "op", "lparen", "rparen"}`
and `value: str`. Numbers are integers or decimals. Operators are `+ - * /`.
Whitespace is skipped. Any other character raises `ValueError` naming the
character and its position.

Acceptance criteria:
- `tokenize("1 + 2.5*(3)")` yields number 1, op +, number 2.5, op *, lparen, number 3, rparen.
- `tokenize("")` yields an empty list.
- `tokenize("1 $ 2")` raises `ValueError` whose message contains `$` and `2`.
- Tests live in `tests/test_tokens.py` and cover all three.
```

Commit it, together with `loop.json`.

### The frontmatter

All six keys are required, one per line, `key: value`:

| Key | Value |
|---|---|
| `id` | the task id; the controller writes it quoted, `"001"` |
| `status` | `pending`, `in_progress`, `blocked` or `done`; start with `status: pending` |
| `attempts` | non-negative integer; start at `0` |
| `no_progress` | non-negative integer; start at `0` |
| `seat_overrides` | inline JSON object, `{}` for none (see section 8) |
| `verify` | `null`, or an inline JSON list of extra shell commands that must exit 0 after an attempt |

A missing key, an unknown status, a non-integer count or bad JSON makes
`task.py` refuse the file. When `task.py pick` hits any invalid file in
`tasks/`, the whole tick is `REFUSED`, so one broken file stops the loop
until you fix it.

### What makes a good brief

Everything after the frontmatter is the brief. Each attempt copies it to
`.loop/sdd/<id>/brief.md` and hands that to the implementer, and the
reviewer gets the acceptance criteria. So:

- Name the files to create or change, and the function signatures.
- Write acceptance criteria as concrete inputs and outputs.
- Name the test file. The implementer writes tests first, and the reviewer
  checks the criteria against them.
- Keep it to one task the implementer can finish in one tick.

### Why `tasks/` is outside `allowed_paths`

The controller edits task frontmatter on every tick (status, attempts,
no_progress) and never commits those edits. If `tasks/` were inside
`allowed_paths`:

- the "uncommitted changes in allowed paths" check would fire on the
  controller's own edits, and every later tick would stop with `UNKNOWN`;
- the commit the controller makes on a Codex seat's behalf
  (`git add -- <allowed_paths>`) would sweep in task files;
- an implementer could change its own task's status without a scope
  violation.

Seats are told never to edit `tasks/`, `loop.json` or `.loop/`. Keeping them
outside `allowed_paths` means the scope check catches it if one does. Expect
`git status` to show your task files as modified while the loop runs.
Commit them when it suits you.

### Which task is picked

`task.py pick tasks` reads `tasks/*.md` in filename order and takes the
first task whose status is `pending` or `in_progress`. An `in_progress` task
is one an earlier tick started and did not finish, so it comes back first.
`blocked` and `done` tasks are skipped. That is why the files are numbered:
`001-...` runs before `002-...`. To hold a task back, give it any status
other than `pending`.

## 4. Dry run

A dry run walks the whole tick without dispatching Claude or Codex, so it
spends nothing from either plan.

### What you type

Commit or stash anything uncommitted under `allowed_paths` first. Then in
`loop.json` set every seat to noop:

```json
"seats": {
  "implementer": {"backend": "noop", "fallback": "noop", "model": "sonnet", "codex_model": "gpt-5.4"},
  "reviewer":    {"backend": "noop", "fallback": "noop", "model": "opus",   "codex_model": "gpt-5.4"},
  "re_reviewer": {"backend": "noop", "fallback": "noop", "model": "sonnet", "codex_model": "gpt-5.4"}
}
```

Keep `model` and `codex_model`; validation still requires them. Then:

```
/loop-sdd tick
```

### What you should see

One ledger line, printed and appended to `.loop/ledger.md`:

```
20261008T101500Z-a1b2 task 001 attempt 1 implementer=noop reviewer=noop check=PASS -> PASS: fresh check passed and reviewer approved
```

The tick id and the four hex characters will differ.

### What it means

The tick took the lock, validated `loop.json`, picked task 001, ran your
check, set the task to `in_progress` with `attempts: 1`, snapshotted the
tree, ran the canned implementer (`bin/noop.py`, which writes a report and
changes no code), checked scope, ran the check again, built an empty review
package, ran the canned reviewer (which always answers `APPROVED`), marked
the task `done`, wrote the run record and released the lock.

- No commit is made. The canned implementer changes nothing.
- The empty diff is not counted as no progress. The noop seats are exempt.
- Any `seat_overrides` in the task are ignored. A noop seat in `loop.json`
  always routes to noop.
- `check=PASS` assumes your suite passes today. If it fails, the dry run
  ends with `RETRY: check FAIL after attempt`, which also proves the flow.
  If the line ends in `UNKNOWN` or `REFUSED`, read the reason and fix that
  before going further.

### Reset by hand

The dry run changed real state. Nothing undoes it for you:

1. Edit the task file: set `status: pending` and `attempts: 0`.
2. Delete `.loop/` (`rm -rf .loop`).
3. Restore the seats in `loop.json` to their real backends.
4. Run `/loop-sdd init` again. It recreates `.loop/` with an empty ledger
   and inbox. A tick run without `.loop/` fails at the lock step.

## 5. First real tick

### What you type

Run one tick by hand and watch it:

```
/loop-sdd tick
```

This one spends quota. The implementer runs on whichever side routing
chooses, then the reviewer, possibly a few fix rounds.

### What you should see

One ledger line, ending in one of the six outcomes. The likely ones on a
first tick:

- `-> PASS: fresh check passed and reviewer approved`. The task is `done`.
- `-> RETRY: check FAIL after attempt`. The implementer committed, but the
  check still fails.
- `-> RETRY: no commits to review`. The implementer committed nothing.

### What a RETRY means

`RETRY` is normal. It means an attempt happened, the budget is not spent,
and the task stays `in_progress`. The next tick picks the same task first
and starts a new attempt from whatever the last one committed. Nothing needs
you.

The attempt counter lives in the task file, not in `.loop/`. Look at
`attempts:` in the frontmatter. Each attempt adds one. When it reaches
`max_attempts_per_task` (default 3) without a pass, the next tick blocks the
task with reason `attempts`. Two attempts in a row with nothing committed
(`no_progress_limit`, default 2) block it with reason `no_progress`.

### Start the loop

When one tick by hand looks right:

```
/loop 2m /loop-sdd tick
```

This fires a tick every two minutes in this Claude Code session. Each tick
does at most one attempt and one review, so it is safe to leave running. A
tick that is still running when the next one fires holds the lock, and the
new one ends `REFUSED: lock held by ...` without touching anything. When no
task is `pending` or `in_progress`, each tick ends `IDLE: no pending task`
until you add one. There is no automatic finish.

## 6. Read what happened

### What you type

```
/loop-sdd status
```

### What you should see

In this order:

1. The full `.loop/inbox.md`, if it has any entry. This is what needs you.
2. One row per task file: id, status, attempts, no_progress, title.
3. The last 10 lines of `.loop/ledger.md`.
4. The newest run record in `.loop/runs/`, pretty-printed.
5. The lock state and the current quota readings, one line each.

`status` is read-only. It changes no file.

### The inbox first

`.loop/inbox.md` collects everything the loop cannot resolve on its own.
Each entry is written by `bin/record.py inbox` and looks like:

```
## task 001 — 2026-10-08 10:15:02 — tick 20261008T101500Z-a1b2

- reason: check
- detail: <last 20 lines of the check output>
- unblock: run the check command by hand, fix the environment, set status: pending
```

`reason` says which rule fired. `detail` is the evidence. `unblock` is the
edit the loop expects from you. Entries for the whole loop, not one task,
use `task -`. The loop only appends. Delete entries yourself once handled.

### One ledger line, field by field

```
20261008T101500Z-a1b2 task 001 attempt 2 implementer=claude reviewer=codex check=PASS -> PASS: fresh check passed and reviewer approved
```

| Field | Meaning |
|---|---|
| `20261008T101500Z-a1b2` | tick id: UTC start time plus four random hex characters; also the run record's file name |
| `task 001` | the task id, or `task -` when no task was picked |
| `attempt 2` | the attempt number this tick worked on; `0` when no attempt started |
| `implementer=claude reviewer=codex` | each seat routed in this tick and the backend it went to, in order; a fix round adds more pairs; absent when no seat ran |
| `check=PASS` | the last check result in this tick: `PASS`, `FAIL`, `UNKNOWN`, or `none` if no check ran |
| `-> PASS` | the outcome |
| `: fresh check ...` | the reason |

The ledger also holds ruling lines:

```
task <id> Ruling: <finding> — <why> — <cost>
```

One is written whenever a review finding is parked rather than
fixed, so no finding disappears without a record.

### The run record

Every tick writes `.loop/runs/<tick_id>.json`. It holds what the ledger line
summarises, in full:

- `tick_id`, `task_id`, `outcome`, `reason`, `attempt`, `elapsed_seconds`;
- `seats`: for each routed seat, `seat`, `backend`, the routing `reason`,
  `blind` (true when the backend was used with unknown quota),
  `quota_before`, `quota_after`, and the seat's `status`;
- `checks`: each check with `when` (`before` or `after`), `status`, and the
  output `tail`;
- `scope`: `changed` and `violations` from the snapshot comparison;
- `review`: the reviewer's verdict.

Start here when a ledger line surprises you.

### The per-task folder

Each task gets `.loop/sdd/<id>/`. The files that matter most:

| File | What it is |
|---|---|
| `base.txt` | the commit the task started from; written once, never rewritten |
| `brief.md` | the task body as handed to the implementer |
| `report-<attempt>.md` | the implementer's report; fix rounds append to it |
| `review-<attempt>.md` | the review package: commits, stat and diff from `base.txt` to `HEAD` |
| `review-<attempt>-reply.md` | the reviewer's reply, verbatim |
| `review-<attempt>-fix<round>.md`, `review-<attempt>-fix<round>-reply.md` | the fix package and re-reviewer reply for each fix round |
| `findings.md` | the open Critical and Important findings |
| `review.json` | the review marker: `verdict`, `base`, `head`, `attempt`, `fix_round` |
| `before.json`, `after.json` | the tree snapshots used for the scope check |
| `seat-implementer.json`, `seat-reviewer.json` | the dispatch handles, used to resume a seat in a fix round |
| `run.json` | the run record handed to `record.py tick` |

`review.json` is what lets an interrupted tick resume. If a tick ran out of
time after the attempt, the next one sees a `PENDING` marker and goes
straight to the review instead of starting a new attempt.

## 7. When it stops

### The six outcomes

| Outcome | What happened | Task status after |
|---|---|---|
| `PASS` | fresh check passed and the reviewer approved (or an approved review was already on record) | `done` |
| `RETRY` | an attempt ran, the check still fails or nothing was committed, budget is left | `in_progress` |
| `IDLE` | no task is `pending` or `in_progress` | unchanged |
| `STOPPED` | a limit fired; the reason says which | `blocked`, or unchanged for `elapsed` and `quota` |
| `UNKNOWN` | the check could not run, the reviewer could not judge, a helper failed, or uncommitted work sat in `allowed_paths` | `blocked` for check and review; unchanged otherwise |
| `REFUSED` | the lock was held, `loop.json` was invalid, or a task file was invalid | unchanged |

### The seven STOPPED reasons

| Reason | Fired when | Task |
|---|---|---|
| `attempts` | `attempts` reached `max_attempts_per_task` | blocked |
| `no_progress` | empty diffs reached `no_progress_limit` | blocked |
| `fix_rounds` | Critical findings still open after `fix_rounds_max` rounds, or a `FIX` verdict with no actionable findings | blocked |
| `scope` | a file outside `allowed_paths` changed | blocked |
| `elapsed` | the tick passed `max_elapsed_seconds_per_tick` before starting another seat | unchanged; next tick resumes |
| `quota` | routing found no backend with room | unchanged; next tick re-checks |
| `seat` | a seat answered `BLOCKED` or `NEEDS_CONTEXT`, crashed, gave an unreadable reply, or left uncommitted changes | blocked |

### Only you unblock

The controller never moves a task out of `blocked` or `done`. Moving
`status: blocked` back to `status: pending` is always your edit, by hand, in
the task file. Nothing does it automatically, and a blocked task is skipped
by every tick until you do.

### The edit for each common case

Read the inbox entry first. Then:

- **`attempts`.** Either raise `max_attempts_per_task` in `loop.json`, or
  set `attempts: 0` in the task file, or split the task into smaller files.
  Then set `status: pending`. If you change neither the limit nor the
  counter, the next tick blocks it again at once.
- **`no_progress`.** The implementer is not committing anything. Make the
  brief clearer, set `no_progress: 0`, and set `status: pending`. Leaving
  the counter at the limit means one more empty attempt blocks it again.
- **`scope`.** The inbox lists every path outside `allowed_paths`. Revert
  them (`git checkout -- <paths>` for working-tree changes; revert the
  commit if the seat committed them), or widen `allowed_paths` if the
  change was right. Then set `status: pending`. The loop does not revert for
  you.
- **review (`UNKNOWN` with reason `review`, or `STOPPED` `fix_rounds`).**
  Read `.loop/sdd/<id>/review-<attempt>-reply.md` and any
  `-fix<round>-reply.md`. Fix the listed Critical findings by hand, or
  split the task, then set `status: pending`.
- **`seat`.** Read the seat's words in the inbox `detail`. If it needed
  context, answer it in the task body (that is the brief the next attempt
  gets). If it left uncommitted changes, commit or discard them. Then set
  `status: pending`.
- **`quota`.** The task is not blocked. Wait for a reset and the next tick
  re-checks, or lower `switch_at` if you want to spend closer to the limit.
  If `.loop/quota-override.json` marks a backend exhausted and you know it
  has reset, delete that entry (section 8).
- **check (`UNKNOWN` with reason `check`).** Run `check_command` by hand,
  fix the environment, then set `status: pending`.

## 8. Route work between Claude and Codex

Before each seat runs, the controller reads the remaining quota on both
sides and asks `bin/quota.py choose` where to send it.

### Where the numbers come from

Neither CLI has a quota command, but both leave numbers on disk:

- **Claude.** Claude Code passes `rate_limits` to your statusline script.
  `/loop-sdd init` adds one line to that script that writes it to
  `~/.claude/usage-cache.json` with a timestamp. The script must contain an
  `input=$(cat)` line for the patch to apply. With no statusline
  configured, init leaves an inbox entry and Claude reads as unknown.
- **Codex.** Codex writes `rate_limits` events into its session logs under
  `~/.codex/sessions/`. The newest `rollout-*.jsonl` file is read.

Each side reports `five_hour` and `seven_day` used percentages and an
`age_seconds`. A reading older than `routing.stale_after_seconds` (default
3600) counts as unknown. Before routing, the controller tries to refresh a
stale Codex reading with one tiny probe. Run `/loop-sdd status` to see both
readings.

### `switch_at`

`routing.switch_at` (default 85) is a used percentage. A backend whose
`five_hour` or `seven_day` is at or above it is skipped.

### `balance` and `fixed`

`routing.policy` picks one of two rules. Each seat has two candidates, its
`backend` and its `fallback`.

- **`balance`** (the default). Of the candidates with a fresh reading under
  `switch_at`, pick the one with the lower `seven_day` usage. A tie goes to
  `backend`. If neither has a fresh reading under `switch_at`, the answer is
  no backend, and the tick stops with `STOPPED` reason `quota`. It never
  dispatches blind.
- **`fixed`**. Use `backend` unless it is at or over `switch_at`. If its
  quota is unknown, use it anyway; the run record marks this `blind: true`.
  If `backend` is over or excluded, use `fallback` only if its reading is
  fresh and under `switch_at`. Otherwise stop with `quota`.

### `quota-override.json`

The reading is a hint; the dispatch error is the truth. When a seat fails
with a rate-limit or usage-limit error, the controller writes
`.loop/quota-override.json`:

```json
{"codex": {"resets_at": 1791500000, "reason": "<first line of the error>"}}
```

Until `resets_at` (epoch seconds) passes, that backend is excluded from
routing. The same seat is retried once on the other side within the tick.
An entry without a usable `resets_at` excludes the backend until you delete
it. You can delete an entry, or the whole file, if you know the backend has
reset.

### `seat_overrides` for an A/B

To compare the two models on similar work, write two similar tasks and give
one of them a `seat_overrides`. The shipped `tasks/002-infix-parser-codex.md`
does this:

```yaml
seat_overrides: {"implementer": {"backend": "codex", "fallback": "claude"}}
```

The rules `task.py` enforces: inline JSON object; seat names are
`implementer`, `reviewer`, `re_reviewer`; allowed keys are `backend`,
`fallback`, `model`, `codex_model`; `backend` and `fallback` must be
`claude` or `codex` (not `noop`) and must differ. Anything else makes
`task.py` refuse the file, and the tick is `REFUSED`.

An override replaces the seat's keys from `loop.json` for that task only.
It does not bypass routing. Under `balance` the side with lower weekly usage
still wins, and swapping `backend` and `fallback` only changes who wins a
tie. To make each task run on the side you named, set `routing.policy` to
`fixed` for the A/B. Even then, an over-quota `backend` falls back. Check
the ledger line (`implementer=codex`) for each task to confirm which side
actually ran before you compare results. Overrides are ignored entirely
when the seat in `loop.json` is `noop`.

## 9. Stop the loop

### What you type

Stop `/loop` in the Claude Code session that runs it, or end that session.
The loop exists only there. Nothing is installed in cron or anywhere else.

### What is left behind

If you stop between ticks, nothing is half-done. If you stop in the middle
of a tick, the task may be left `in_progress` with a `review.json` marker.
That is fine: the next tick resumes the review or starts a new attempt.

### What is safe to delete

- `.loop/` is runtime state: the ledger, inbox, run records, per-task
  folders, quota readings, the override file and the lock. It is in
  `.gitignore`. You can delete it, then run `/loop-sdd init` to recreate it.
  Do this when no task is `in_progress`. Otherwise the next tick takes a new
  `base.txt` from the current `HEAD`, and the review package no longer shows
  the commits earlier attempts made.
- `tasks/` and `loop.json` are your inputs. Do not delete them to "reset"
  the loop. Task status and the attempt counters live in the task files;
  edit them instead.

### The lock file

`.loop/lock` exists while a tick runs. Each tick takes it at the start and
releases it at the end, on every exit path the controller controls. A tick
that finds it held ends `REFUSED` and never deletes it.

Delete it by hand in one case only: the tick that held it is dead (you
killed the session mid-tick) and no tick is running now. `/loop-sdd status`
shows the owner and age. When the age is far beyond
`max_elapsed_seconds_per_tick`, ticks also leave an inbox entry with reason
`lock`. Confirm nothing is running, then:

```bash
rm .loop/lock
```

## Where things are

| Path | Purpose |
|---|---|
| `loop.json` | check command, limits, allowed paths, routing, seats |
| `tasks/NNN-<slug>.md` | one task per file; frontmatter is state, body is the brief |
| `.loop/inbox.md` | everything that needs a human, with the edit to make |
| `.loop/ledger.md` | one line per tick, plus ruling lines |
| `.loop/runs/<tick_id>.json` | the full run record for each tick |
| `.loop/sdd/<id>/` | per-task brief, reports, review packages, replies, findings, `review.json` |
| `.loop/lock` | held while a tick runs |
| `.loop/quota.json` | the last quota reading used for routing |
| `.loop/quota-override.json` | backends marked exhausted after a rate-limit error |
| `~/.claude/usage-cache.json` | Claude quota, written by your statusline script |
| `~/.codex/sessions/` | Codex session logs, read for Codex quota |
| `.claude/skills/loop-sdd/` or `~/.claude/skills/loop-sdd/` | the skill: `SKILL.md`, `actions/`, `seats/`, `bin/` |
