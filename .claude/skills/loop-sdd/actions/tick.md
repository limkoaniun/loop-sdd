# tick

One bounded run. One attempt per tick. Set these mentally and use them in
every command below:

- `H=python3 .claude/skills/loop-sdd/bin` (helper directory)
- `SKILL=.claude/skills/loop-sdd` (seat templates live at `$SKILL/seats/`)
- `WS=$(pwd)`; every other path is relative to the workspace.

**Inbox entry** means exactly:
`$H/record.py inbox --loop-dir .loop --task <task_id, or - when none> --tick <tick_id> --reason <reason> --detail "<detail>" --unblock "<what the human edits>"`.
Wherever a step says "inbox", give reason, detail and unblock.

**Ruling** means
`$H/record.py ruling --loop-dir .loop --task <task_id> --finding "<finding>" --why "<why>" --cost "<cost of leaving it>"`.

**Helper failure rule.** Any non-zero helper exit that a step does not map
explicitly (2, 3, a traceback's 1, or anything else) → outcome `UNKNOWN`, reason `<helper>: <first stderr line>`, task
status unchanged, inbox entry with reason `helper` and unblock "inspect
.loop/runs/<tick_id>.json and the helper's stderr", then record (step 11) and
release the lock. If `record.py tick` itself fails, still release the lock and
print the error. The controller's own tooling never leaves the lock held.

Record what you learn as you go in a run record you will hand to
`record.py tick` at the end. Start it now:

```json
{"tick_id": "<UTC %Y%m%dT%H%M%SZ>-<4 random hex>", "task_id": null, "outcome": null,
 "reason": null, "attempt": 0, "elapsed_seconds": 0, "seats": [], "checks": [],
 "scope": null, "review": null}
```

Note the start time. "Elapsed" below means seconds since it.

## 1. Lock

`$H/lock.py take .loop/lock --owner <tick_id>`.
Exit 3 → outcome `REFUSED`, reason "lock held by <owner> for <age>s",
record, print, stop. No token was taken, so there is nothing to release. Do
not delete the lock. If age is far beyond `max_elapsed_seconds_per_tick`,
add an inbox entry (`--task -`, reason `lock`, detail "lock held <age>s by
<owner>", unblock "check for a dead owner, then delete .loop/lock") so a
human can check.

Keep the token. Every other exit path ends with
`$H/lock.py release .loop/lock --token <token>` after recording.

## 2. Load

`$H/loopcfg.py validate loop.json`. Exit 2 → `REFUSED`,
reason is the first error line. Then read `loop.json` once.

## 3. Pick

`$H/task.py pick tasks`. Exit 2 → `REFUSED` with the
helper's error. `null` → `IDLE`, reason "no pending task". Otherwise set
`task_id`, and keep `path`, `attempts`, `no_progress`, `seat_overrides`,
`verify`.

Make `mkdir -p .loop/sdd/<task_id>`. If `.loop/sdd/<task_id>/base.txt` does
not exist, write `git rev-parse HEAD` to it (the task base; it is never
rewritten).

## 4. Fresh check

Run the check command from `loop.json` in the workspace with a 120-second
timeout, capture exit code,
the last 20 lines of output (stdout and stderr together), and the last
stderr line. `check_ran_marker` is the regex from `loop.json` (default
`passed|failed|error` when absent). Map:
- exit 0 → `PASS`;
- exit in `check_fail_exits` (from `loop.json`, default `[1]`) AND the captured
  tail matches `check_ran_marker` → `FAIL` (the tests ran and some failed);
- anything else, including a check that timed out after 120s or crashed, and a
  listed exit without a marker match (runner missing, collection error) →
  `UNKNOWN`, reason "check did not run: <last stderr line>".

Append `{"when": "before", "status": ..., "tail": ...}` to `checks`.

`review.json` always has the shape
`{"verdict": "PENDING"|"FIX"|"APPROVED", "base": <task base>, "head": <HEAD at write>, "attempt": <n>, "fix_round": <int>}`,
plus, only while a fix round awaits its re-review, `"fix_base": <sha>` and
`"pending_rereview": true`.

- `UNKNOWN` → `$H/task.py set <path> status=blocked`, inbox reason `check`
  (detail: the tail; unblock "run the check command by hand, fix the
  environment, set status: pending"), outcome `UNKNOWN`, stop.
- `PASS`, the task is `in_progress`, and `review.json` exists:
  - `head` differs from `git rev-parse HEAD` → the tree moved under the
    loop: delete `review.json`, inbox reason `review` (detail "review marker
    stale"; unblock "read .loop/sdd/<task_id>/review-<attempt>-reply.md and any -fix<round>-reply.md, set status: pending"), and continue as a fresh attempt.
  - `"verdict": "APPROVED"` → `$H/task.py set <path> status=done`, outcome
    `PASS`, reason "fresh check passed; approved review on record", stop.
  - For both PENDING and FIX below, first restore from `review.json`:
    `attempt` (into the record too), `fix_round`, `fix_base` and
    `pending_rereview`, so report and package paths match the interrupted
    run.
  - `"verdict": "PENDING"` → the attempt already happened; only the review is
    owed. Skip steps 5 to 9, go to step 10's review dispatch (the package
    uses `base.txt`).
  - `"verdict": "FIX"` → go to the **Fix loop**, reading the open findings
    for `[FINDINGS]` from `.loop/sdd/<task_id>/findings.md`. If
    `pending_rereview` is true, resume at fix-loop step 7 (re-review the
    stored `fix_base`..HEAD package) without dispatching the implementer.
    Otherwise continue from round `fix_round + 1`, so `fix_rounds_max`
    binds across ticks. Skip steps 5 to 10.
- Otherwise continue. (A `PASS` on a `pending` task just means the task adds
  new behavior; the attempt still runs.)

## 5. Budget

If `attempts >= max_attempts_per_task`: `$H/task.py set <path> status=blocked`,
inbox reason `attempts` (detail "attempts exhausted"; unblock "raise
max_attempts_per_task or split the task, then set status: pending"), outcome
`STOPPED` reason `attempts`, stop. This sits after the resume checks so a
task with a PENDING or APPROVED marker is finished, not blocked.

## 6. Uncommitted work

`git status --porcelain -- <allowed_paths...>`. If the output is non-empty,
work is sitting uncommitted where the implementer would write, and no
reviewer would ever see it: outcome `UNKNOWN`, reason "uncommitted changes
in allowed paths", task unchanged, inbox reason `seat` (detail: the file
list; unblock "commit or discard them"), stop.

## 7. Attempt

If elapsed ≥ `max_elapsed_seconds_per_tick` → outcome `STOPPED` reason
`elapsed`, task unchanged, stop.

**Route first.** Run **Routing a seat** below with seat `implementer`
BEFORE changing any task state. `backend: null` stops with `STOPPED` reason
`quota` and the task genuinely unchanged.

Only then: `$H/task.py set <path> status=in_progress attempts=<attempts+1>`.
Set `attempt` in the record.

Snapshot now, after the frontmatter edit, so the task file's own change is
not inside the attempt's window:
`$H/snapshot.py take . > .loop/sdd/<task_id>/before.json`.
`BASE=$(git rev-parse HEAD)` (this attempt's start; used for scope and the
fresh-diff test only).

Write the brief: copy the task file body (everything after the frontmatter)
to `.loop/sdd/<task_id>/brief.md`. Report path is
`.loop/sdd/<task_id>/report-<attempt>.md`.

Dispatch using
`$SKILL/seats/implementer.md` with every bracket filled: `[BRIEF_FILE]`,
`[REPORT_FILE]`, `[ALLOWED_PATHS]` (from loop.json, space-separated),
`[CHECK_COMMAND]`, `[WORKDIR]` (absolute workspace path). Store the handle
in `.loop/sdd/<task_id>/seat-implementer.json`.

**Reading an implementer reply** (also used by the fix loop). Its first line
is `Status: <TOKEN>`; match the whole token
exactly (never a substring test: `DONE` is a prefix of `DONE_WITH_CONCERNS`).
Reviewer and re-reviewer replies start with `Verdict: <TOKEN>`; match those
the same way (`ADDRESSED` is a substring of `NOT ADDRESSED`). A reply whose
first line is not one of the allowed tokens is a seat failure.
- `DONE` or `DONE_WITH_CONCERNS` → continue; concerns become a named risk in
  the reviewer's `[GLOBAL_CONSTRAINTS]`. If the reply says
  `Commits: none (sandbox); subject: <subject>` (a Codex seat cannot write
  `.git`), commit on its behalf: `git add -- <allowed_paths...>` then
  `git commit -m "<subject>"`. Never add the report file or anything
  outside `allowed_paths`. If there is nothing to commit, treat the attempt
  as an empty diff in step 8.
  Then run `git status --porcelain -- <allowed_paths...>`. If it is
  non-empty and the reply was not `Commits: none (sandbox)` → seat failure:
  `$H/task.py set <path> status=blocked`, inbox reason `seat` (detail
  "uncommitted changes after DONE: <files>"; unblock "commit or discard
  them, set status: pending"), outcome `STOPPED` reason `seat`, stop.
- `NEEDS_CONTEXT` or `BLOCKED` → `$H/task.py set <path> status=blocked`,
  inbox reason `seat` (detail: the seat's words; unblock "answer in the
  brief or inspect the seat's words, set status: pending"), outcome
  `STOPPED` reason `seat`, stop.
- A crashed seat, or a first line that is not an allowed token → same:
  blocked, inbox reason `seat`, detail the seat's words or "unparseable
  reply", outcome `STOPPED` reason `seat`.
- A failure whose text mentions a rate limit or usage limit → see
  **Rate-limit errors**.

## 8. Scope

`$H/snapshot.py take . > .loop/sdd/<task_id>/after.json`, then
`$H/snapshot.py scope .loop/sdd/<task_id>/before.json .loop/sdd/<task_id>/after.json --allowed <allowed_paths...>`.
Put the result in `scope`.

- `violations` non-empty → `$H/task.py set <path> status=blocked`, inbox
  reason `scope` (detail: every path; unblock "git checkout -- <paths>, set
  status: pending"), outcome `STOPPED` reason `scope`, stop. Do not revert.
- `changed` empty → `$H/task.py set <path> no_progress=<no_progress+1>`. If
  that is now ≥ `no_progress_limit` → `status=blocked`, inbox reason
  `no_progress` (unblock "clarify the brief, set status: pending"), `STOPPED`
  reason `no_progress`, stop.
  A noop implementer seat is exempt: skip the no_progress increment and
  continue; build the package anyway and dispatch the noop reviewer.
- `changed` non-empty → `$H/task.py set <path> no_progress=0`.

## 9. Fresh check again

Same as step 4, `"when": "after"`. Also run each command in `verify` if the
task set one; any non-zero there counts as `FAIL`.

- `FAIL` → outcome `RETRY`, reason "check FAIL after attempt", task stays
  `in_progress`, stop.
- `UNKNOWN` → blocked, inbox reason `check` (unblock as in step 4), outcome
  `UNKNOWN`, stop.
- `PASS` → continue.

## 10. Review

`HEAD=$(git rev-parse HEAD)`. Build the package first (it is read-only):
`$H/review_package.py $(cat .loop/sdd/<task_id>/base.txt) $HEAD .loop/sdd/<task_id>/review-<attempt>.md`.
The package covers the whole task (base.txt..HEAD), not just this attempt.

If `empty` is true, nothing was committed: delete
`.loop/sdd/<task_id>/review.json` if present, then
`$H/task.py set <path> no_progress=<no_progress+1>`. If that reaches
`no_progress_limit` → `status=blocked`, inbox reason `no_progress` (unblock
"clarify the brief, set status: pending"), outcome `STOPPED` reason
`no_progress`, stop. Otherwise outcome `RETRY`, reason "no commits to
review", stop. Never leave a PENDING marker on an empty package.
A noop implementer seat is exempt: skip the no_progress increment and
continue; build the package anyway and dispatch the noop reviewer (write
the PENDING marker below as usual).

Otherwise write `.loop/sdd/<task_id>/review.json` as
`{"verdict": "PENDING", "base": <base.txt>, "head": <HEAD>, "attempt": <attempt>, "fix_round": 0}`
so a tick that runs out of time here resumes at the review, not at a new
attempt. If elapsed ≥ limit → `STOPPED` reason `elapsed`, task stays
`in_progress`, stop.

Route seat `reviewer`. Dispatch `$SKILL/seats/reviewer.md` with `[BRIEF_FILE]`,
`[REPORT_FILE]`, `[DIFF_FILE]`, `[GLOBAL_CONSTRAINTS]` (the task's
acceptance criteria plus any implementer concerns, verbatim). Store the
handle in `seat-reviewer.json`.

Persist the reviewer's reply verbatim to
`.loop/sdd/<task_id>/review-<attempt>-reply.md` (reviewer seats cannot write
under `.loop/`), and write the open Critical and Important findings to
`.loop/sdd/<task_id>/findings.md` (empty when none). Every item under the
reviewer's "### Spec compliance" goes into `findings.md` as an Important
finding, alongside the Critical and Important ones. Rewrite `review.json`
with the verdict (same shape, same `fix_round: 0`) and put the verdict in
the record's `review`.

- `APPROVED` → `$H/task.py set <path> status=done`, outcome `PASS`, reason
  "fresh check passed and reviewer approved", stop.
- `UNKNOWN` → blocked, inbox reason `review` (detail: the reviewer's words;
  unblock "read .loop/sdd/<task_id>/review-<attempt>-reply.md and any -fix<round>-reply.md, set status: pending"), outcome `UNKNOWN`, stop.
- `FIX` → fix loop, starting at round 1 with the reviewer's findings.

## Fix loop

The controller keeps the open-findings list itself (Critical and Important,
verbatim) in `.loop/sdd/<task_id>/findings.md`, the only copy that survives
a tick. Round counter starts at `fix_round + 1` (1 on first entry).

On entry (from step 10 or a FIX resume): if `findings.md` has no open
Critical or Important item, do not dispatch. `$H/task.py set <path> status=blocked`,
inbox reason `review` (detail "FIX verdict with no actionable findings; see
review-<attempt>-reply.md"; unblock "read the reply, fix by hand or set
status: pending"), outcome `STOPPED` reason `fix_rounds`, stop.

For each round up to `fix_rounds_max`:

1. If elapsed ≥ limit → `STOPPED` reason `elapsed`, task stays `in_progress`,
   `review.json` verdict `FIX`, stop.
2. Minor findings: one ruling each saying why it is parked, and drop them
   from the list.
3. `FIX_BASE=$(git rev-parse HEAD)`. Take the before snapshot:
   `$H/snapshot.py take . > .loop/sdd/<task_id>/before-fix<round>.json`.
   Route seat `implementer`. If the routed backend matches the stored
   handle's backend, resume that handle; if it differs, dispatch fresh on the
   routed backend using the template's fresh-dispatch path, filling the same
   placeholders as step 7 (`[BRIEF_FILE]`, `[REPORT_FILE]`,
   `[ALLOWED_PATHS]`, `[CHECK_COMMAND]`, `[WORKDIR]`) plus the open
   findings, and overwrite the handle file. Either
   way the instruction is the open findings verbatim and "append a fix report
   to [REPORT_FILE]".
   Handle the reply exactly as **Reading an implementer reply** in step 7
   (exact `Status:` token; `BLOCKED`, `NEEDS_CONTEXT` or unparseable →
   blocked + inbox reason `seat`; `Commits: none (sandbox)` → commit on its
   behalf with the same `git add -- <allowed_paths>` rule; then the same
   `git status --porcelain` check for uncommitted work).
4. After the seat returns, take the after snapshot
   (`after-fix<round>.json`) and run `snapshot.py scope` as in step 8. A
   violation stops as in step 8.
5. Fresh check as in step 9. `FAIL` → `RETRY`; `UNKNOWN` → blocked.
6. `$H/review_package.py $FIX_BASE $(git rev-parse HEAD) .loop/sdd/<task_id>/review-<attempt>-fix<round>.md`.
   If `empty` is true, the fix committed nothing: apply the empty-package
   rule of step 10 (delete `review.json`, bump `no_progress`, `RETRY` or
   `STOPPED` reason `no_progress`). A noop implementer seat is exempt: skip
   the no_progress increment and continue; build the package anyway and
   dispatch the noop reviewer.
   Otherwise rewrite `review.json` with verdict `FIX`, the current HEAD,
   `fix_base: $FIX_BASE`, `pending_rereview: true`, and `fix_round` left at
   its PREVIOUS value (it advances only in step 8, after the re-review is
   read).
7. Route seat `reviewer`. If the routed backend matches the stored reviewer
   handle's backend, resume it using `$SKILL/seats/re-reviewer.md`; if it
   differs, dispatch fresh on the routed backend using the template's
   fresh-dispatch path and overwrite the handle file. Either way fill
   `[BRIEF_FILE]`, `[REPORT_FILE]`, `[DIFF_FILE]` (the fix package path) and
   `[FINDINGS]` (the open list, from `findings.md`).
8. Persist the reply verbatim to
   `.loop/sdd/<task_id>/review-<attempt>-fix<round>-reply.md`. Update the
   open list: remove findings the reply marks `ADDRESSED` under
   "### Per finding", add any Critical or Important under "### New
   breakage", and rewrite `findings.md`. Rewrite `review.json` with the
   current HEAD, `fix_round: <round>`, and `pending_rereview` cleared.
   Empty list (verdict `ADDRESSED`) → `review.json` verdict `APPROVED`,
   `$H/task.py set <path> status=done`, outcome `PASS`, stop.
   Verdict `NOT ADDRESSED` → next round with the open list.

After the last round with findings open: ruling for every open Important.
If any Critical remains → `status=blocked`, inbox reason `fix_rounds`
(detail: the Critical findings; unblock "fix the listed Critical findings by
hand or split the task, then set status: pending"), outcome `STOPPED` reason
`fix_rounds`, stop. If only Importants were parked → treat as `ADDRESSED`:
`review.json` verdict `APPROVED`, task `done`, outcome `PASS`.

## 11. Record and unlock

Fill `outcome`, `reason`, `elapsed_seconds`. Write the record to
`.loop/sdd/<task_id>/run.json` (or `.loop/last-run.json` when there is no
task) and run `$H/record.py tick --loop-dir .loop --json <that file>`.
Release the lock only if a token was taken (not on `REFUSED` at the lock
step). Releasing happens even when `record.py tick` failed or a helper
failure ended the tick (see the Helper failure rule). Print the ledger line
as your only output.

## Routing a seat

1. `$H/quota.py read > .loop/quota.json`.
2. For a side whose reading is `null` or whose `age_seconds` exceeds
   `routing.stale_after_seconds`, and which is NOT present in
   `.loop/quota-override.json` with a future `resets_at` (those are known
   exhausted; skip the refresh):
   - Codex: refresh with one probe through `mcp__codex__codex`, prompt
     `reply OK`, `model` = the seat's `codex_model`, `sandbox: read-only`,
     `cwd` = workspace. Then re-run `quota.py read`.
   - Claude: your own turns have been redrawing the statusline. If it is
     still stale, add an inbox entry with reason `quota`, detail "claude
     statusline cache stale; run /loop-sdd init", unblock "run /loop-sdd
     init", and continue.
3. `$H/quota.py choose --readings .loop/quota.json --config loop.json --seat <seat> --override .loop/quota-override.json --seat-overrides '<task seat_overrides JSON, or {} when none>'`.
   Pass `--override` even if the file does not exist; the helper treats a
   missing file as `{}`.
4. `backend: null` → outcome `STOPPED` reason `quota`, task unchanged
   (inbox reason `quota`, detail "no backend available", unblock "wait for
   the reset, or lower switch_at"), stop.
5. Append `{"seat": ..., "backend": ..., "reason": ..., "blind": ..., "quota_before": <readings>}`
   to the record's `seats`. After the seat returns, run `quota.py read` again
   and add `quota_after` and `status`.
6. `backend: noop` → run the matching `noop.py` command instead of
   dispatching, and treat its stdout as the reply.

## Rate-limit errors

When a dispatch fails and the error text mentions a rate limit or usage
limit:

1. Write or update `.loop/quota-override.json`:
   `{"<backend>": {"resets_at": <resets_at for the window that is over, or now + 3600 if unknown>, "reason": "<error text, first line>"}}`.
2. Re-run **Routing a seat** for the same seat. If it yields the other
   backend, dispatch there; this is the same attempt and the same report
   path. If it yields `null` → `STOPPED` reason `quota`.
3. If the failing dispatch was a resumed handle (fix loop), the other backend
   has no handle: dispatch FRESH there using the matching template's
   fresh-dispatch path with `[BRIEF_FILE]`, `[REPORT_FILE]`, the open
   findings, and for a re-reviewer also `[DIFF_FILE]` (the current fix
   package path). If routing yields `null` → `STOPPED` reason `quota`, task stays
   `in_progress`, `review.json` keeps verdict `FIX`.
4. Never retry the same backend inside the tick.
