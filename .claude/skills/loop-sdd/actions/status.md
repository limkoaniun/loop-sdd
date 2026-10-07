# status

Read-only. Nothing here changes a file.

1. Print `.loop/inbox.md` in full if it has any entry beyond the heading.
   This comes first because it is what needs a human.
2. For every file in `tasks/`, `python3 $SKILL/bin/task.py show <file>`
   and print one row: id, status, attempts, no_progress, title. If `show`
   exits 2, print the error in that row.
3. Print the last 10 lines of `.loop/ledger.md`.
4. Print the newest file in `.loop/runs/` by name, pretty-printed.
5. `python3 $SKILL/bin/lock.py status .loop/lock` and
   `python3 $SKILL/bin/quota.py read`, one line each.
