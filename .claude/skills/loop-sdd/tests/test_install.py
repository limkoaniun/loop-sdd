import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL = ROOT / ".claude" / "skills" / "loop-sdd"


def sh(*args, env=None):
    return subprocess.run(["bash", str(ROOT / "install.sh"), *map(str, args)], capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, cwd=ROOT)


def test_user_install_symlinks(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    r = sh("--user", env={"HOME": str(home)})
    assert r.returncode == 0, r.stderr
    link = home / ".claude" / "skills" / "loop-sdd"
    assert link.is_symlink() and link.resolve() == SKILL.resolve()
    assert "/loop-sdd init" in r.stdout
    r = sh("--user", env={"HOME": str(home)})          # idempotent
    assert r.returncode == 0 and link.is_symlink()


def test_user_install_refuses_real_dir(tmp_path):
    home = tmp_path / "home"; target = home / ".claude" / "skills" / "loop-sdd"
    target.mkdir(parents=True); (target / "keep").write_text("x")
    r = sh("--user", env={"HOME": str(home)})
    assert r.returncode == 1 and (target / "keep").exists() and "refus" in (r.stdout + r.stderr).lower()


def test_project_install_copies(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir(); (proj / ".git").mkdir()
    r = sh(proj)
    assert r.returncode == 0, r.stderr
    dest = proj / ".claude" / "skills" / "loop-sdd"
    assert (dest / "SKILL.md").exists() and (dest / "bin" / "loopcfg.py").exists() and not dest.is_symlink()
    assert not (dest / "tests").exists()                 # tests are not shipped into projects
    r = sh(proj)
    assert r.returncode == 1                             # exists, no --force
    assert sh(proj, "--force").returncode == 0


def test_project_install_warns_without_git(tmp_path):
    proj = tmp_path / "proj"; proj.mkdir()
    r = sh(proj)
    assert r.returncode == 0 and "not a git repository" in (r.stdout + r.stderr)


def test_usage_error(tmp_path):
    assert sh().returncode == 2 and sh("--bogus").returncode == 2


def test_no_hardcoded_skill_path_in_actions_or_seats():
    for p in list((SKILL / "actions").glob("*.md")) + list((SKILL / "seats").glob("*.md")):
        assert ".claude/skills/loop-sdd" not in p.read_text(), p.name
    assert "$SKILL" in (SKILL / "SKILL.md").read_text()


def test_force_refuses_to_delete_source(tmp_path):
    r = sh(ROOT, "--force")
    assert r.returncode == 1 and (SKILL / "SKILL.md").exists() and "refused" in (r.stdout + r.stderr)


def test_force_refuses_symlinked_home_skills(tmp_path):
    home = tmp_path / "home"; (home / ".claude" / "skills").mkdir(parents=True)
    proj = tmp_path / "proj"; (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "skills").symlink_to(home / ".claude" / "skills")
    r = sh(proj, "--force", env={"HOME": str(home)})
    assert r.returncode == 1 and "refused" in (r.stdout + r.stderr)
