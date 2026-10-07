import json
import subprocess


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("one\n")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "a.txt").write_text("two\n")
    git(tmp_path, "commit", "-qam", "feat: change a")
    return base, git(tmp_path, "rev-parse", "HEAD")


def test_package_has_three_sections(run, tmp_path):
    base, head = repo(tmp_path)
    out = tmp_path / "pkg.md"
    r = run("review_package", base, head, out, "--repo", tmp_path)
    assert r.returncode == 0, r.stderr
    meta = json.loads(r.stdout)
    assert meta == {"path": str(out), "commits": 1, "empty": False}
    text = out.read_text()
    assert "## Commits" in text and "feat: change a" in text
    assert "## Stat" in text and "a.txt" in text
    assert "## Diff" in text and "-one" in text and "+two" in text


def test_empty_range_is_flagged(run, tmp_path):
    base, head = repo(tmp_path)
    out = tmp_path / "pkg.md"
    meta = json.loads(run("review_package", head, head, out, "--repo", tmp_path).stdout)
    assert meta["commits"] == 0 and meta["empty"] is True


def test_bad_ref(run, tmp_path):
    repo(tmp_path)
    r = run("review_package", "nope", "HEAD", tmp_path / "x", "--repo", tmp_path)
    assert r.returncode == 2
