import re
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def test_skill_md_frontmatter_and_actions():
    text = (SKILL / "SKILL.md").read_text()
    assert text.startswith("---\nname: loop-sdd\n")
    assert "argument-hint: init|tick|status" in text
    for action in ("init", "tick", "status"):
        assert f"actions/{action}.md" in text


def test_tick_references_every_helper_and_template():
    text = (SKILL / "actions" / "tick.md").read_text()
    for helper in ("loopcfg.py validate", "lock.py take", "lock.py release", "snapshot.py take", "snapshot.py scope",
                   "review_package.py", "task.py pick", "task.py set", "quota.py read", "quota.py choose",
                   "record.py tick", "record.py inbox", "record.py ruling", "noop.py"):
        assert helper in text, helper
    assert "check_fail_exits" in text
    for seat in ("seats/implementer.md", "seats/reviewer.md", "seats/re-reviewer.md"):
        assert seat in text
    for outcome in ("PASS", "RETRY", "IDLE", "STOPPED", "UNKNOWN", "REFUSED"):
        assert re.search(rf"\b{outcome}\b", text), outcome
    for reason in ("attempts", "no_progress", "fix_rounds", "scope", "elapsed", "quota", "seat"):
        assert f"`{reason}`" in text, reason
    assert "one attempt per tick" in text.lower()


def test_init_patches_statusline_and_status_reads_inbox():
    assert "statusline_patch.py" in (SKILL / "actions" / "init.md").read_text()
    assert "loopcfg.py init" in (SKILL / "actions" / "init.md").read_text()
    status = (SKILL / "actions" / "status.md").read_text()
    assert "inbox.md" in status and "task.py" in status


def test_tick_snapshots_after_marking_in_progress():
    text = (SKILL / "actions" / "tick.md").read_text()
    assert "task.py set <path> status=in_progress" in text and "before.json" in text
    assert text.index("task.py set <path> status=in_progress") < text.index("before.json")
