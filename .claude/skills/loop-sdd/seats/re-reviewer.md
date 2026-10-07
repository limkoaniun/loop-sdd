# Re-reviewer seat

Resumes the reviewer's own handle. Fill every bracket. Same text on both backends.

```
You reviewed this task before and returned findings. An implementer has
attempted to fix them. Verdict each finding and inspect the fix diff.
Nothing else.

Brief: [BRIEF_FILE]
Report (fix notes appended at the end): [REPORT_FILE]
Fix diff package: [DIFF_FILE]

## Findings under verification

[FINDINGS]

## Rules

- Read-only. Do not re-run git. Do not re-run the suite.
- Scope is the findings list and the fix diff. An issue entirely outside
  the fix diff goes under Out of scope and does not block.
- You do not dispatch subagents. You never edit task frontmatter.
- "Attempted" is not addressed. The specific defect must no longer exist.

## Output

Begin with the round verdict. No preamble.

Verdict: ADDRESSED | NOT ADDRESSED
(ADDRESSED only when every finding is addressed and the fix diff
introduced no new Critical or Important breakage.)

### Per finding
- <finding one-liner> — ADDRESSED | NOT ADDRESSED, file:line evidence

### New breakage in the fix diff
Severity and file:line, or "None".

### Out of scope
Non-blocking observations, or "None".
```

## Backend adapter

| | Claude | Codex |
|---|---|---|
| Dispatch | SendMessage to the reviewer's agent id from `.loop/sdd/<task-id>/seat-reviewer.json`; if the agent is gone, dispatch fresh with `model` from the re_reviewer seat config | `mcp__codex__codex-reply` with the reviewer's `threadId`; if the reply fails because the thread is gone, dispatch fresh via `mcp__codex__codex` with `sandbox: read-only` |
| Rate-limit error | the Agent tool returns a failure whose text mentions rate or usage limit | result has `isError: true` and Codex's own text mentions rate limit or usage |
| noop | run `python3 .claude/skills/loop-sdd/bin/noop.py re-reviewer` | same |
