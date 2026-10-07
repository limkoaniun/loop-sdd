# init

Run once per project. Safe to re-run.

1. `python3 .claude/skills/loop-sdd/bin/loopcfg.py validate loop.json`.
   On exit 2, print the errors and stop. Nothing else runs.
2. `mkdir -p .loop/runs .loop/sdd` and ensure `.loop/` is listed in
   `.gitignore` (append the line if missing).
3. Create `.loop/ledger.md` and `.loop/inbox.md` if missing, each with a
   one-line heading (`# ledger`, `# inbox`).
4. Find the statusline script: read `statusLine.command` from
   `~/.claude/settings.json`. If it is `sh <path>` or `bash <path>` or a bare
   path, run `python3 .claude/skills/loop-sdd/bin/statusline_patch.py <path>`.
   If there is no statusLine configured, write to the inbox with reason
   `init`, detail "no statusline script; Claude quota will read as unknown",
   unblock "configure a statusline command, then re-run init", and continue.
5. `python3 .claude/skills/loop-sdd/bin/quota.py read` and print the result,
   so the user sees which sides are readable right now.
6. Report: config valid, directories present, statusline patched or not,
   quota readings, and the start command `/loop 2m /loop-sdd tick`.
