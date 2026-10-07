import json

CACHE_LINE = """printf '%s' "$input" | jq -c '{rate_limits: .rate_limits, written_at: now}' > "$HOME/.claude/usage-cache.json" 2>/dev/null"""


def test_patch_inserts_after_input_line(run, tmp_path):
    s = tmp_path / "statusline.sh"
    s.write_text('#!/bin/sh\ninput=$(cat)\nmodel=$(echo "$input" | jq -r .model.display_name)\n')
    r = run("statusline_patch", s)
    assert r.returncode == 0 and json.loads(r.stdout) == {"patched": True}
    lines = s.read_text().splitlines()
    assert lines[1] == "input=$(cat)" and lines[2] == CACHE_LINE and lines[3].startswith("model=")


def test_patch_is_idempotent(run, tmp_path):
    s = tmp_path / "statusline.sh"
    s.write_text('input=$(cat)\n')
    run("statusline_patch", s)
    r = run("statusline_patch", s)
    assert json.loads(r.stdout) == {"patched": False, "reason": "already patched"}
    assert s.read_text().count("usage-cache.json") == 1


def test_patch_refuses_without_input_line(run, tmp_path):
    s = tmp_path / "statusline.sh"; s.write_text('echo hi\n')
    r = run("statusline_patch", s)
    assert r.returncode == 2 and s.read_text() == 'echo hi\n'
