import json

TASK = """---
id: "001"
status: pending
attempts: 0
no_progress: 0
seat_overrides: {}
verify: null
---
# Add a parser

Body text.
"""


def test_pick_first_pending_by_filename(run, tmp_path):
    (tmp_path / "002-b.md").write_text(TASK.replace('"001"', '"002"'))
    (tmp_path / "001-a.md").write_text(TASK.replace("status: pending", "status: done"))
    (tmp_path / "003-c.md").write_text(TASK.replace('"001"', '"003"').replace("pending", "in_progress"))
    out = json.loads(run("task", "pick", tmp_path).stdout)
    assert out["id"] == "002" and out["status"] == "pending" and out["title"] == "Add a parser"


def test_pick_none(run, tmp_path):
    (tmp_path / "001-a.md").write_text(TASK.replace("status: pending", "status: blocked"))
    assert json.loads(run("task", "pick", tmp_path).stdout) is None


def test_set_updates_and_preserves_body(run, tmp_path):
    p = tmp_path / "001-a.md"; p.write_text(TASK)
    r = run("task", "set", p, "status=in_progress", "attempts=2", 'seat_overrides={"implementer":{"backend":"codex"}}')
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "in_progress" and out["attempts"] == 2
    assert out["seat_overrides"] == {"implementer": {"backend": "codex"}}
    text = p.read_text()
    assert "Body text." in text and "attempts: 2" in text


def test_invalid_status_refused(run, tmp_path):
    p = tmp_path / "001-a.md"; p.write_text(TASK.replace("status: pending", "status: maybe"))
    r = run("task", "pick", tmp_path)
    assert r.returncode == 2 and "001-a.md" in r.stderr and "status" in r.stderr


def test_string_attempts_refused(run, tmp_path):
    p = tmp_path / "001-a.md"; p.write_text(TASK.replace("attempts: 0", 'attempts: "2"'))
    r = run("task", "pick", tmp_path)
    assert r.returncode == 2 and "attempts" in r.stderr


def test_set_rejects_bad_value(run, tmp_path):
    p = tmp_path / "001-a.md"; p.write_text(TASK)
    r = run("task", "set", p, "status=finished")
    assert r.returncode == 2
    assert "status: pending" in p.read_text()


def test_pick_missing_dir_exits_2(run, tmp_path):
    r = run("task", "pick", tmp_path / "nope")
    assert r.returncode == 2 and "error:" in r.stderr


def test_pick_validates_every_file(run, tmp_path):
    (tmp_path / "001-a.md").write_text(TASK)
    (tmp_path / "002-b.md").write_text(TASK.replace('"001"', '"002"').replace("status: pending", "status: maybe"))
    r = run("task", "pick", tmp_path)
    assert r.returncode == 2 and "002-b.md" in r.stderr and "status" in r.stderr


def test_pick_unicode_digit_attempts_exits_2(run, tmp_path):
    (tmp_path / "001-a.md").write_text(TASK.replace("attempts: 0", "attempts: \u0663"), encoding="utf-8")
    r = run("task", "pick", tmp_path)
    assert r.returncode == 2 and "attempts" in r.stderr and "Traceback" not in r.stderr


def test_pick_non_utf8_exits_2(run, tmp_path):
    (tmp_path / "001-a.md").write_bytes(TASK.encode() + b"\xff\xfe")
    r = run("task", "pick", tmp_path)
    assert r.returncode == 2 and "not UTF-8" in r.stderr and "Traceback" not in r.stderr


def test_seat_overrides_validated(run, tmp_path):
    bad = [
        '{"planner": {"backend": "codex"}}',
        '{"implementer": {"backend": "gpt"}}',
        '{"implementer": {"backend": "codex", "fallback": "codex"}}',
        '{"implementer": {"backend": "noop"}}',
    ]
    for value in bad:
        (tmp_path / "001-a.md").write_text(TASK.replace("seat_overrides: {}", f"seat_overrides: {value}"))
        r = run("task", "pick", tmp_path)
        assert r.returncode == 2 and "seat_overrides" in r.stderr and "Traceback" not in r.stderr, value
    good = '{"implementer": {"backend": "codex", "fallback": "claude", "model": "opus"}}'
    (tmp_path / "001-a.md").write_text(TASK.replace("seat_overrides: {}", f"seat_overrides: {good}"))
    assert run("task", "pick", tmp_path).returncode == 0
