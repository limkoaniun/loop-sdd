from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOC = ROOT / "docs" / "TUTORIAL.md"

REQUIRED_HEADINGS = [
    "## 1. Install", "## 2. Create loop.json", "## 3. Write your first task", "## 4. Dry run",
    "## 5. First real tick", "## 6. Read what happened", "## 7. When it stops", "## 8. Route work between Claude and Codex",
    "## 9. Stop the loop",
]
REQUIRED_STRINGS = [
    "./install.sh --user", "/loop-sdd init", "/loop-sdd tick", "/loop-sdd status", "/loop 2m /loop-sdd tick",
    "check_fail_exits", "check_ran_marker", "allowed_paths", "seat_overrides", "status: pending", "status: blocked",
    ".loop/inbox.md", ".loop/ledger.md", ".loop/runs/", "noop", "switch_at", "balance", "fixed",
    "PASS", "RETRY", "IDLE", "STOPPED", "UNKNOWN", "REFUSED",
]


def test_tutorial_structure():
    text = DOC.read_text()
    for h in REQUIRED_HEADINGS:
        assert h in text, h
    for s in REQUIRED_STRINGS:
        assert s in text, s
    assert "TUTORIAL.md" in (ROOT / "README.md").read_text()
