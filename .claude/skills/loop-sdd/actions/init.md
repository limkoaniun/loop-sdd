# init

Run once per project. Safe to re-run.

1. `python3 .claude/skills/loop-sdd/bin/loopcfg.py validate loop.json`.
   On exit 2, print the errors and stop. Nothing else runs.
2. Run the `check_command` from `loop.json` once in the workspace. Capture
   the exit code and the last 20 lines of output. `check_ran_marker` is the
   regex from `loop.json` (default `passed|failed|error` when absent). Unless
   the exit is 0 or 1 AND the tail matches the marker, print the exit code
   and tail, then "init refused: check command cannot run", and stop (a tick
   would read every result as `UNKNOWN`). Otherwise print the exit code and
   the tail's last line, and continue.
3. `mkdir -p .loop/runs .loop/sdd` and ensure `.loop/` is listed in
   `.gitignore` (append the line if missing).
4. Create `.loop/ledger.md` and `.loop/inbox.md` if missing, each with a
   one-line heading (`# ledger`, `# inbox`).
5. Find the statusline script: read `statusLine.command` from
   `~/.claude/settings.json`. If it is `sh <path>` or `bash <path>` or a bare
   path, run `python3 .claude/skills/loop-sdd/bin/statusline_patch.py <path>`.
   If there is no statusLine configured, run
   `python3 .claude/skills/loop-sdd/bin/record.py inbox --loop-dir .loop --task - --tick init --reason init --detail "no statusline script; Claude quota will read as unknown" --unblock "configure a statusline command, then re-run init"`
   and continue.
6. `python3 .claude/skills/loop-sdd/bin/quota.py read` and print the result,
   so the user sees which sides are readable right now.
7. Report: config valid, directories present, statusline patched or not,
   quota readings, and the start command `/loop 2m /loop-sdd tick`.
