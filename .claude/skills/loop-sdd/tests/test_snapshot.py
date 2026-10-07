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
    write(tmp_path, "src/a.py", "x")
    write(tmp_path, ".loop/ledger.md", "x")
    write(tmp_path, "src/__pycache__/a.pyc", "x")
    write(tmp_path, ".git/HEAD", "x")
    snap = take(run, tmp_path)
    assert set(snap) == {"src/a.py"}
    assert len(snap["src/a.py"]) == 64


def test_scope_reports_changed_and_violations(run, tmp_path):
    write(tmp_path, "src/a.py", "1")
    write(tmp_path, "tests/t.py", "1")
    write(tmp_path, "loop.json", "{}")
    before = tmp_path / "before.json"
    before.write_text(json.dumps(take(run, tmp_path)))
    write(tmp_path, "src/a.py", "2")          # modified, allowed
    write(tmp_path, "src/b.py", "1")          # added, allowed
    (tmp_path / "tests/t.py").unlink()        # removed, allowed
    write(tmp_path, "loop.json", "{ }")       # modified, violation
    write(tmp_path, "tasks/001.md", "x")      # added, violation
    write(tmp_path, ".loop/x", "x")           # ignored
    after = tmp_path / "after.json"
    after.write_text(json.dumps(take(run, tmp_path)))
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
