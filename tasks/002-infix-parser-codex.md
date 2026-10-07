---
id: "002"
status: pending
attempts: 0
no_progress: 0
seat_overrides: {"implementer": {"backend": "codex", "fallback": "claude"}}
verify: null
---
# Add a parser for infix expressions

Add `src/calc/parse.py` with `parse(tokens: list[Token]) -> Node` building a
tree where `Node` is a dataclass with `op: str | None`, `value: float | None`,
`left: Node | None`, `right: Node | None`. Precedence: `*` and `/` bind
tighter than `+` and `-`; all are left-associative; parentheses override.
Use the tokenizer from task 001.

Acceptance criteria:
- `parse(tokenize("1 + 2 * 3"))` is `+` with left 1 and right (`*` 2 3).
- `parse(tokenize("(1 + 2) * 3"))` is `*` with left (`+` 1 2) and right 3.
- `parse(tokenize("1 +"))` raises `ValueError` mentioning "unexpected end".
- Tests live in `tests/test_parse.py` and cover all three.
