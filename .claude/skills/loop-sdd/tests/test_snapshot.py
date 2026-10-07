import json


def take(run, root):
    r = run("snapshot", "take", root)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_take_hashes_files_and_skips_runtime_dirs(run, tmp_path):
    root = tmp_path / "ws"
    write(root, "src/a.py", "x")
    write(root, ".loop/ledger.md", "x")
    write(root, "src/__pycache__/a.pyc", "x")
    write(root, ".git/HEAD", "x")
    snap = take(run, root)
    assert set(snap) == {"src/a.py"}
    assert len(snap["src/a.py"]) == 64


def test_scope_reports_changed_and_violations(run, tmp_path):
    root = tmp_path / "ws"
    write(root, "src/a.py", "1")
    write(root, "tests/t.py", "1")
    write(root, "loop.json", "{}")
    before = tmp_path / "before.json"
    before.write_text(json.dumps(take(run, root)))
    write(root, "src/a.py", "2")          # modified, allowed
    write(root, "src/b.py", "1")          # added, allowed
    (root / "tests/t.py").unlink()        # removed, allowed
    write(root, "loop.json", "{ }")       # modified, violation
    write(root, "tasks/001.md", "x")      # added, violation
    write(root, ".loop/x", "x")           # ignored
    after = tmp_path / "after.json"
    after.write_text(json.dumps(take(run, root)))
    r = run("snapshot", "scope", before, after, "--allowed", "src/", "tests/")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["changed"] == ["loop.json", "src/a.py", "src/b.py", "tasks/001.md", "tests/t.py"]
    assert out["violations"] == ["loop.json", "tasks/001.md"]


def test_allowed_without_trailing_slash_is_a_directory(run, tmp_path):
    before = tmp_path / "b.json"; before.write_text("{}")
    after = tmp_path / "a.json"; after.write_text(json.dumps({"src/calc/x.py": "h", "srcfoo.py": "h"}))
    out = json.loads(run("snapshot", "scope", before, after, "--allowed", "src").stdout)
    assert out["violations"] == ["srcfoo.py"]


def test_exact_file_entry_allowed(run, tmp_path):
    before = tmp_path / "b.json"; before.write_text("{}")
    after = tmp_path / "a.json"; after.write_text(json.dumps({"NOTES.md": "h", "NOTES.md.bak": "h"}))
    out = json.loads(run("snapshot", "scope", before, after, "--allowed", "NOTES.md").stdout)
    assert out["violations"] == ["NOTES.md.bak"]


def test_take_missing_root_exits_2(run, tmp_path):
    r = run("snapshot", "take", tmp_path / "nope")
    assert r.returncode == 2 and "error:" in r.stderr


def test_scope_non_object_json_exits_2(run, tmp_path):
    before = tmp_path / "b.json"; before.write_text("[]")
    after = tmp_path / "a.json"; after.write_text("{}")
    r = run("snapshot", "scope", before, after, "--allowed", "src/")
    assert r.returncode == 2 and "error:" in r.stderr
