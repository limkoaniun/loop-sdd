import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BIN = ROOT / ".claude" / "skills" / "loop-sdd" / "bin"


def helper(name, *args):
    return subprocess.run([sys.executable, str(BIN / f"{name}.py"), *map(str, args)], capture_output=True, text=True, cwd=ROOT)


def test_shipped_loop_json_validates():
    r = helper("loopcfg", "validate", ROOT / "loop.json")
    assert r.returncode == 0, r.stderr


def test_shipped_tasks_pick_first():
    r = helper("task", "pick", ROOT / "tasks")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["id"] == "001" and out["status"] == "pending"


def test_second_task_routes_implementer_to_codex():
    out = json.loads(helper("task", "show", ROOT / "tasks" / "002-infix-parser-codex.md").stdout)
    assert out["seat_overrides"] == {"implementer": {"backend": "codex", "fallback": "claude"}}


def test_loop_dir_ignored():
    assert ".loop/" in (ROOT / ".gitignore").read_text().splitlines()
