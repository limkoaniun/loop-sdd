# tick

One bounded run. One attempt per tick. Set `SKILL=.claude/skills/loop-sdd`
and `WS=$(pwd)` mentally; every path below is relative to the workspace.

Record what you learn as you go in a run record you will hand to
`record.py tick` at the end. Start it now:

```json
{"tick_id": "<UTC %Y%m%dT%H%M%SZ>-<4 random hex>", "task_id": null, "outcome": null,
 "reason": null, "attempt": 0, "elapsed_seconds": 0, "seats": [], "checks": [],
 "scope": null, "review": null}
```

Note the start time. "Elapsed" below means seconds since it.

## 1. Lock

`python3 $SKILL/bin/lock.py take .loop/lock --owner <tick_id>`.
Exit 3 → outcome `REFUSED`, reason "lock held by <owner> for <age>s",
record, print, stop. Do not delete the lock. If age is far beyond
`max_elapsed_seconds_per_tick`, say so in the inbox so a human can check
for a dead owner.

Keep the token. Every exit path below ends with
`python3 $SKILL/bin/lock.py release .loop/lock --token <token>` after
recording.

## 2. Load

`python3 $SKILL/bin/loopcfg.py validate loop.json`. Exit 2 → `REFUSED`,
reason is the first error line. Then read `loop.json` once.

## 3. Pick

`python3 $SKILL/bin/task.py pick tasks`. Exit 2 → `REFUSED` with the
helper's error. `null` → `IDLE`, reason "no pending task". Otherwise set
`task_id`, and keep `path`, `attempts`, `no_progress`, `seat_overrides`,
`verify`.

Make `mkdir -p .loop/sdd/<task_id>`.

## 4. Budget

If `attempts >= max_attempts_per_task`: `task.py set <path> status=blocked`,
`record.py inbox` with reason `attempts`, outcome `STOPPED` reason
`attempts`, stop.

## 5. Fresh check

Run the check command from `loop.json` in the workspace, capture exit code
and the last 20 lines. Map: exit 0 → `PASS`, exit 1 → `FAIL`, anything
else (could not run, timed out after 120s, crashed) → `UNKNOWN`. Append
`{"when": "before", "status": ..., "tail": ...}` to `checks`.

- `UNKNOWN` → `task.py set <path> status=blocked`, inbox reason `check`
  with the tail, outcome `UNKNOWN`, stop.
- `PASS` and the task is `in_progress` and `.loop/sdd/<task_id>/review.json`
  exists with `"verdict": "APPROVED"` and its `head` equals `git rev-parse HEAD`
  → `task.py set <path> status=done`, outcome `PASS`, reason "fresh check
  passed; approved review on record", stop.
- `PASS` and the task is `in_progress` and `review.json` has
  `"verdict": "PENDING"` or `"FIX"` with `head` equal to `git rev-parse HEAD`
  → skip steps 6 to 9 and go to step 10 (the attempt already happened; only
  the review is owed). Set `BASE` from `review.json`'s `base`.
- Otherwise continue. (A `PASS` on a `pending` task just means the task adds
  new behavior; the attempt still runs.)

## 6. Snapshot

`python3 $SKILL/bin/snapshot.py take . > .loop/sdd/<task_id>/before.json`.
`BASE=$(git rev-parse HEAD)`.

## 7. Attempt

If elapsed ≥ `max_elapsed_seconds_per_tick` → outcome `STOPPED` reason
`elapsed`, task unchanged, stop.

`task.py set <path> status=in_progress attempts=<attempts+1>`. Set
`attempt` in the record.

Write the brief: copy the task file body (everything after the frontmatter)
to `.loop/sdd/<task_id>/brief.md`. Report path is
`.loop/sdd/<task_id>/report-<attempt>.md`.

Route: see **Routing a seat** below with seat `implementer`. Dispatch using
`seats/implementer.md` with every bracket filled: `[BRIEF_FILE]`,
`[REPORT_FILE]`, `[ALLOWED_PATHS]` (from loop.json, space-separated),
`[CHECK_COMMAND]`, `[WORKDIR]` (absolute workspace path). Store the handle
in `.loop/sdd/<task_id>/seat-implementer.json`.

Read the reply. Its first line is `Status: <TOKEN>`; match the whole token
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
- `NEEDS_CONTEXT` → `task.py set status=blocked`, inbox reason `seat` with the
  question, unblock "answer in the brief, set status: pending", outcome
  `STOPPED` reason `seat`, stop.
- `BLOCKED` → same as above with the seat's words.
- Any failure → see **Rate-limit errors**. A non-quota failure is `STOPPED`
  reason `seat`.

## 8. Scope

`python3 $SKILL/bin/snapshot.py take . > .loop/sdd/<task_id>/after.json`, then
`python3 $SKILL/bin/snapshot.py scope .loop/sdd/<task_id>/before.json .loop/sdd/<task_id>/after.json --allowed <allowed_paths...>`.
Put the result in `scope`.

- `violations` non-empty → `task.py set status=blocked`, inbox reason `scope`
  naming every path, unblock "inspect and restore the path from git, set
  status: pending", outcome `STOPPED` reason `scope`, stop. Do not revert.
- `changed` empty → `task.py set no_progress=<no_progress+1>`. If that is now
  ≥ `no_progress_limit` → blocked, inbox reason `no_progress`, `STOPPED`
  reason `no_progress`, stop.
- `changed` non-empty → `task.py set no_progress=0`.

## 9. Fresh check again

Same as step 5, `"when": "after"`. Also run each command in `verify` if the
task set one; any non-zero there counts as `FAIL`.

- `FAIL` → outcome `RETRY`, reason "check FAIL after attempt", task stays
  `in_progress`, stop.
- `UNKNOWN` → blocked, inbox reason `check`, outcome `UNKNOWN`, stop.
- `PASS` → continue.

## 10. Review

`HEAD=$(git rev-parse HEAD)`. Before anything else write
`.loop/sdd/<task_id>/review.json` as
`{"verdict": "PENDING", "head": <HEAD>, "base": <BASE>, "attempt": <attempt>}`
so a tick that runs out of time here resumes at the review, not at a new
attempt. If elapsed ≥ limit → `STOPPED` reason `elapsed`, task stays
`in_progress`, stop.
`python3 $SKILL/bin/review_package.py $BASE $HEAD .loop/sdd/<task_id>/review-<attempt>.md`.
If `empty` is true, the implementer committed nothing: treat as `RETRY`
with reason "no commits to review".

Route seat `reviewer`. Dispatch `seats/reviewer.md` with `[BRIEF_FILE]`,
`[REPORT_FILE]`, `[DIFF_FILE]`, `[GLOBAL_CONSTRAINTS]` (the task's
acceptance criteria plus any implementer concerns, verbatim). Store the
handle in `seat-reviewer.json`.

Write `.loop/sdd/<task_id>/review.json` as
`{"verdict": <verdict>, "head": <HEAD>, "attempt": <attempt>}` and put the
verdict in the record's `review`.

- `APPROVED` → `task.py set status=done`, outcome `PASS`, reason "fresh check
  passed and reviewer approved", stop.
- `UNKNOWN` → blocked, inbox reason `review` with the reviewer's words,
  outcome `UNKNOWN`, stop.
- `FIX` → fix loop.

## Fix loop

Round counter starts at 1. For each round up to `fix_rounds_max`:

1. If elapsed ≥ limit → `STOPPED` reason `elapsed`, task stays `in_progress`,
   `review.json` verdict `FIX`, stop.
2. Collect the Critical and Important findings verbatim. Minor findings:
   `record.py ruling` each with why it is parked, and drop them from the loop.
3. `FIX_BASE=$(git rev-parse HEAD)`. Resume the implementer handle with the
   findings verbatim and "append a fix report to [REPORT_FILE]".
4. Scope check as in step 8 (new snapshot pair). A violation stops as in
   step 8.
5. Fresh check as in step 9. `FAIL` → `RETRY`; `UNKNOWN` → blocked.
6. `review_package.py $FIX_BASE $(git rev-parse HEAD) .loop/sdd/<task_id>/review-<attempt>-fix<round>.md`.
7. Resume the reviewer handle using `seats/re-reviewer.md` with `[FINDINGS]`.
8. `ADDRESSED` → update `review.json` to `APPROVED` with the new head,
   `task.py set status=done`, outcome `PASS`, stop.
   `NOT ADDRESSED` → next round with the still-open findings.

After the last round with findings open: park every open Important with a
`record.py ruling` line. If any Critical remains → blocked, inbox reason
`fix_rounds` listing them, outcome `STOPPED` reason `fix_rounds`, stop.
If only Importants were parked → treat as `ADDRESSED`.

## 11. Record and unlock

Fill `outcome`, `reason`, `elapsed_seconds`. Write the record to
`.loop/sdd/<task_id>/run.json` (or `.loop/last-run.json` when there is no
task) and run `python3 $SKILL/bin/record.py tick --loop-dir .loop --json <that file>`.
Release the lock. Print the ledger line as your only output.

## Routing a seat

1. `python3 $SKILL/bin/quota.py read > .loop/quota.json`.
2. For a side whose reading is `null` or whose `age_seconds` exceeds
   `routing.stale_after_seconds`:
   - Codex: refresh with one probe through `mcp__codex__codex`, prompt
     `reply OK`, `model` = the seat's `codex_model`, `sandbox: read-only`,
     `cwd` = workspace. Then re-run `quota.py read`.
   - Claude: your own turns have been redrawing the statusline. If it is
     still stale, write an inbox entry with reason `quota` and detail
     "claude statusline cache stale; run /loop-sdd init", and continue.
3. `python3 $SKILL/bin/quota.py choose --readings .loop/quota.json --config loop.json --seat <seat> --override .loop/quota-override.json --seat-overrides '<task seat_overrides JSON>'`.
4. `backend: null` → outcome `STOPPED` reason `quota`, task unchanged, stop.
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
3. Never retry the same backend inside the tick.
