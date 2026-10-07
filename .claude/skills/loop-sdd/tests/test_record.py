import json


def test_tick_writes_run_and_ledger(run, tmp_path):
    rec = {"tick_id": "T1", "task_id": "001", "outcome": "RETRY", "reason": "check FAIL after attempt", "attempt": 2,
           "elapsed_seconds": 5, "seats": [{"seat": "implementer", "backend": "codex", "status": "DONE"}],
           "checks": [{"when": "before", "status": "FAIL"}, {"when": "after", "status": "FAIL"}],
           "scope": {"changed": [], "violations": []}, "review": None}
    f = tmp_path / "rec.json"; f.write_text(json.dumps(rec))
    r = run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert json.loads((tmp_path / ".loop" / "runs" / "T1.json").read_text()) == rec
    line = (tmp_path / ".loop" / "ledger.md").read_text().strip()
    assert line == "T1 task 001 attempt 2 implementer=codex check=FAIL -> RETRY: check FAIL after attempt"
    assert out["ledger_line"] == line


def test_tick_idle_without_task(run, tmp_path):
    rec = {"tick_id": "T2", "task_id": None, "outcome": "IDLE", "reason": "no pending task", "attempt": 0, "seats": [], "checks": []}
    f = tmp_path / "rec.json"; f.write_text(json.dumps(rec))
    run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert (tmp_path / ".loop" / "ledger.md").read_text().strip() == "T2 task - attempt 0 check=none -> IDLE: no pending task"


def test_tick_rejects_missing_fields(run, tmp_path):
    f = tmp_path / "rec.json"; f.write_text(json.dumps({"tick_id": "T3"}))
    r = run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert r.returncode == 2 and "outcome" in r.stderr


def test_inbox_entry(run, tmp_path):
    r = run("record", "inbox", "--loop-dir", tmp_path / ".loop", "--task", "001", "--tick", "T1",
            "--reason", "scope", "--detail", "changed loop.json", "--unblock", "restore loop.json, set status: pending")
    assert r.returncode == 0, r.stderr
    text = (tmp_path / ".loop" / "inbox.md").read_text()
    assert "## task 001" in text and "tick T1" in text and "reason: scope" in text
    assert "changed loop.json" in text and "unblock: restore loop.json" in text


def test_ruling_line(run, tmp_path):
    run("record", "ruling", "--loop-dir", tmp_path / ".loop", "--task", "001", "--finding", "long function", "--why", "readable", "--cost", "none")
    assert (tmp_path / ".loop" / "ledger.md").read_text().strip() == "task 001 Ruling: long function — readable — none"


def test_tick_rejects_tick_id_with_separator(run, tmp_path):
    rec = {"tick_id": "../evil", "task_id": None, "outcome": "IDLE", "reason": "", "attempt": 0, "seats": [], "checks": []}
    f = tmp_path / "rec.json"; f.write_text(json.dumps(rec))
    r = run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert r.returncode == 2 and "error:" in r.stderr
    assert not (tmp_path / "evil.json").exists() and not (tmp_path / ".loop" / "ledger.md").exists()


def test_tick_rejects_non_list_seats_and_non_object_root(run, tmp_path):
    f = tmp_path / "rec.json"
    f.write_text(json.dumps({"tick_id": "T", "task_id": None, "outcome": "IDLE", "reason": "", "attempt": 0, "seats": None, "checks": []}))
    r = run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert r.returncode == 2 and "seats" in r.stderr
    f.write_text("null")
    r = run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert r.returncode == 2 and "error:" in r.stderr


def test_tick_without_reason_has_no_suffix(run, tmp_path):
    rec = {"tick_id": "T9", "task_id": "001", "outcome": "RETRY", "reason": "", "attempt": 1, "seats": [], "checks": [{"when": "after", "status": "FAIL"}]}
    f = tmp_path / "rec.json"; f.write_text(json.dumps(rec))
    run("record", "tick", "--loop-dir", tmp_path / ".loop", "--json", f)
    assert (tmp_path / ".loop" / "ledger.md").read_text().strip() == "T9 task 001 attempt 1 check=FAIL -> RETRY"


def test_tick_unwritable_loop_dir_exits_2(run, tmp_path):
    rec = {"tick_id": "T9", "task_id": None, "outcome": "IDLE", "reason": "x", "attempt": 0, "seats": [], "checks": []}
    f = tmp_path / "rec.json"; f.write_text(json.dumps(rec))
    blocker = tmp_path / "not-a-dir"; blocker.write_text("file")
    r = run("record", "tick", "--loop-dir", blocker, "--json", f)
    assert r.returncode == 2 and "error:" in r.stderr and "Traceback" not in r.stderr
    r = run("record", "inbox", "--loop-dir", blocker, "--task", "-", "--tick", "T9", "--reason", "x", "--detail", "d", "--unblock", "u")
    assert r.returncode == 2 and "error:" in r.stderr and "Traceback" not in r.stderr
    r = run("record", "ruling", "--loop-dir", blocker, "--task", "-", "--finding", "f", "--why", "w", "--cost", "c")
    assert r.returncode == 2 and "error:" in r.stderr and "Traceback" not in r.stderr
