import re
from pathlib import Path

SEATS = Path(__file__).resolve().parent.parent / "seats"

EXPECTED = {
    "implementer.md": {"[BRIEF_FILE]", "[REPORT_FILE]", "[ALLOWED_PATHS]", "[CHECK_COMMAND]", "[WORKDIR]"},
    "reviewer.md": {"[BRIEF_FILE]", "[REPORT_FILE]", "[DIFF_FILE]", "[GLOBAL_CONSTRAINTS]"},
    "re-reviewer.md": {"[BRIEF_FILE]", "[REPORT_FILE]", "[DIFF_FILE]", "[FINDINGS]"},
}
WORDS = {
    "implementer.md": ["DONE", "DONE_WITH_CONCERNS", "BLOCKED", "NEEDS_CONTEXT", "never delete, skip, or loosen"],
    "reviewer.md": ["APPROVED", "FIX", "UNKNOWN", "Critical", "Important", "Minor", "always Critical"],
    "re-reviewer.md": ["ADDRESSED", "NOT ADDRESSED"],
}


def test_templates_have_placeholders_and_contract_words():
    for name, placeholders in EXPECTED.items():
        text = (SEATS / name).read_text()
        found = set(re.findall(r"\[[A-Z_]+\]", text))
        assert placeholders <= found, f"{name} missing {placeholders - found}"
        for word in WORDS[name]:
            assert word in text, f"{name} missing {word!r}"
        assert "## Backend adapter" in text
        assert "subagent" in text.lower() and "frontmatter" in text.lower()
