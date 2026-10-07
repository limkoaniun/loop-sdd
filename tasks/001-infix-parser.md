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
