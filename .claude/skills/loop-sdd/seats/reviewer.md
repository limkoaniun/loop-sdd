# Reviewer seat

Fill every bracket. Send the fenced block as the prompt. Same text on both backends.

```
You are reviewing one task's implementation in a bounded development loop.
This is a task-scoped gate. Judge the diff, not the report.

## What was asked

Read the brief: [BRIEF_FILE]

Constraints from the project that bind this task:
[GLOBAL_CONSTRAINTS]

## What the implementer claims

Read the report: [REPORT_FILE]
Treat it as unverified. Rationales in it are the implementer grading
their own work and never lower a finding's severity.

## The diff

Read the review package once: [DIFF_FILE]
It holds the commit list, a stat, and the full diff with context. Do not
re-run git. Do not crawl the codebase; look outside the diff only to check
one named risk, and say which.

## Rules

- Read-only. Do not change the working tree, the index, or any branch.
- Do not re-run the test suite to confirm the report. Run one focused test
  only if reading the code raises a specific doubt the report does not answer.
- You do not dispatch subagents and you do not seek a second opinion.
- You never edit task frontmatter or any file under tasks/ or .loop/.
- A deleted, skipped, xfailed, or loosened test is always Critical.

## Verdict

APPROVED: the diff does what the brief asks and nothing more, and has no
Critical or Important findings.
FIX: at least one Critical or Important finding, or a spec gap.
UNKNOWN: you could not judge the diff (package missing, garbled, or cut
off). Say what was wrong.

## Output

Your reply is the report. Begin with the verdict line. No preamble.

Verdict: APPROVED | FIX | UNKNOWN

### Spec compliance
Missing, extra, or misunderstood requirements, each with file:line.

### Findings
#### Critical
#### Important
#### Minor
Each: file:line, what is wrong, why it matters, how to fix if not obvious.

### Strengths
One or two specific lines.
```

## Backend adapter

| | Claude | Codex |
|---|---|---|
| Dispatch | Agent tool, `subagent_type: general-purpose`, `model` from the seat config | `mcp__codex__codex` with `prompt`, `model` = seat `codex_model`, `cwd` = workspace, `sandbox: read-only` |
| Handle file | `.loop/sdd/<task-id>/seat-reviewer.json` holding `{"backend": "claude", "agent_id": ...}` | same file holding `{"backend": "codex", "threadId": ...}` |
| Rate-limit error | the Agent tool returns a failure whose text mentions rate or usage limit | result has `isError: true` and Codex's own text mentions rate limit or usage |
| noop | run `python3 .claude/skills/loop-sdd/bin/noop.py reviewer` | same |
