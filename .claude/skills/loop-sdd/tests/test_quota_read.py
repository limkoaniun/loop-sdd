import json
import os
import time


def claude_cache(tmp_path, written_at, five=23.5, seven=41.2):
    p = tmp_path / "usage-cache.json"
    p.write_text(json.dumps({
        "rate_limits": {"five_hour": {"used_percentage": five, "resets_at": 1000},
                        "seven_day": {"used_percentage": seven, "resets_at": 2000}},
        "written_at": written_at,
    }))
    return p


def codex_sessions(tmp_path, primary, secondary, mtime):
    d = tmp_path / "sessions" / "2026" / "10" / "07"
    d.mkdir(parents=True)
    f = d / "rollout-2026-10-07T22-53-52-abc.jsonl"
    event = {"type": "event_msg", "payload": {"type": "token_count", "info": None,
             "rate_limits": {"primary": primary, "secondary": secondary}}}
    f.write_text(json.dumps({"type": "session_meta"}) + "\n" + json.dumps(event) + "\n")
    os.utime(f, (mtime, mtime))
    return tmp_path / "sessions"


def test_both_sides_parsed(run, tmp_path):
    now = 1_800_000_000
    cache = claude_cache(tmp_path, now - 12)
    sessions = codex_sessions(
        tmp_path,
        {"used_percent": 8.0, "window_minutes": 300, "resets_at": 3000},
        {"used_percent": 15.0, "window_minutes": 10080, "resets_at": 4000},
        now - 3400,
    )
    r = run("quota", "read", "--claude-cache", cache, "--codex-sessions", sessions, "--now", now)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["claude"]["five_hour"] == 23.5 and out["claude"]["seven_day"] == 41.2
    assert out["claude"]["age_seconds"] == 12 and out["claude"]["source"] == "statusline-cache"
    assert out["codex"]["five_hour"] == 8.0 and out["codex"]["seven_day"] == 15.0
    assert out["codex"]["age_seconds"] == 3400 and out["codex"]["source"] == "session-log"
    assert out["codex"]["resets_at"] == {"five_hour": 3000, "seven_day": 4000}


def test_codex_weekly_only_window(run, tmp_path):
    now = 1_800_000_000
    sessions = codex_sessions(tmp_path, {"used_percent": 0.0, "window_minutes": 10080, "resets_at": 99}, None, now - 5)
    out = json.loads(run("quota", "read", "--claude-cache", tmp_path / "missing", "--codex-sessions", sessions, "--now", now).stdout)
    assert out["claude"] is None
    assert out["codex"]["five_hour"] is None and out["codex"]["seven_day"] == 0.0


def test_missing_sources_are_null(run, tmp_path):
    out = json.loads(run("quota", "read", "--claude-cache", tmp_path / "nope", "--codex-sessions", tmp_path / "nope").stdout)
    assert out == {"claude": None, "codex": None}


def test_newest_rollout_wins(run, tmp_path):
    now = 1_800_000_000
    sessions = codex_sessions(tmp_path, {"used_percent": 50.0, "window_minutes": 300, "resets_at": 1}, None, now - 100)
    old = tmp_path / "sessions" / "2026" / "10" / "01"; old.mkdir(parents=True)
    f = old / "rollout-old.jsonl"
    f.write_text(json.dumps({"payload": {"rate_limits": {"primary": {"used_percent": 99.0, "window_minutes": 300, "resets_at": 1}, "secondary": None}}}) + "\n")
    os.utime(f, (now - 9000, now - 9000))
    out = json.loads(run("quota", "read", "--claude-cache", tmp_path / "nope", "--codex-sessions", sessions, "--now", now).stdout)
    assert out["codex"]["five_hour"] == 50.0


def rollout(tmp_path, lines, mtime):
    d = tmp_path / "sessions" / "2026" / "10" / "07"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "rollout-2026-10-07T22-53-52-abc.jsonl"
    f.write_bytes(b"".join(l if isinstance(l, bytes) else (json.dumps(l) + "\n").encode() for l in lines))
    os.utime(f, (mtime, mtime))
    return tmp_path / "sessions"


def test_codex_age_from_event_timestamp(run, tmp_path):
    now = 1_800_000_000
    ev = {"timestamp": "2027-01-15T08:00:00Z", "payload": {"rate_limits": {"primary": {"used_percent": 1.0, "window_minutes": 300, "resets_at": 5}, "secondary": None}}}
    sessions = rollout(tmp_path, [ev], now - 9999)
    out = json.loads(run("quota", "read", "--claude-cache", tmp_path / "nope", "--codex-sessions", sessions, "--now", now).stdout)
    assert out["codex"]["age_seconds"] == 0


def test_codex_null_payload_line_is_skipped(run, tmp_path):
    now = 1_800_000_000
    good = {"payload": {"info": {"rate_limits": {"primary": {"used_percent": 2.0, "window_minutes": 300, "resets_at": 7}, "secondary": None}}}}
    bad = {"payload": None, "note": "rate_limits"}
    sessions = rollout(tmp_path, [good, bad], now - 5)
    r = run("quota", "read", "--claude-cache", tmp_path / "nope", "--codex-sessions", sessions, "--now", now)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["codex"]["five_hour"] == 2.0


def test_codex_truncated_utf8_tail_is_tolerated(run, tmp_path):
    now = 1_800_000_000
    good = {"payload": {"rate_limits": {"primary": {"used_percent": 3.0, "window_minutes": 300, "resets_at": "soon"}, "secondary": None}}}
    sessions = rollout(tmp_path, [good, b'{"rate_limits": "\xe2\x82'], now - 5)
    r = run("quota", "read", "--claude-cache", tmp_path / "nope", "--codex-sessions", sessions, "--now", now)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["codex"]
    assert out["five_hour"] == 3.0 and out["resets_at"]["five_hour"] is None
