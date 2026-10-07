import json


def test_take_then_refuse(run, tmp_path):
    lock = tmp_path / "lock"
    r = run("lock", "take", lock, "--owner", "tick-1")
    assert r.returncode == 0, r.stderr
    first = json.loads(r.stdout)
    assert first["taken"] is True and first["token"]
    r = run("lock", "take", lock, "--owner", "tick-2")
    assert r.returncode == 3
    second = json.loads(r.stdout)
    assert second["taken"] is False and second["owner"] == "tick-1"
    assert "token" not in second


def test_release_with_wrong_token_refused(run, tmp_path):
    lock = tmp_path / "lock"
    run("lock", "take", lock, "--owner", "t")
    r = run("lock", "release", lock, "--token", "nope")
    assert r.returncode == 3
    assert lock.exists()


def test_release_with_right_token(run, tmp_path):
    lock = tmp_path / "lock"
    token = json.loads(run("lock", "take", lock, "--owner", "t").stdout)["token"]
    r = run("lock", "release", lock, "--token", token)
    assert r.returncode == 0
    assert not lock.exists()


def test_status(run, tmp_path):
    lock = tmp_path / "lock"
    assert json.loads(run("lock", "status", lock).stdout) == {"held": False}
    run("lock", "take", lock, "--owner", "t")
    s = json.loads(run("lock", "status", lock).stdout)
    assert s["held"] is True and s["owner"] == "t" and s["age_seconds"] >= 0
    assert "token" not in s


def test_release_missing_lock(run, tmp_path):
    r = run("lock", "release", tmp_path / "lock", "--token", "x")
    assert r.returncode == 3


def test_status_with_malformed_created_at(run, tmp_path):
    lock = tmp_path / "lock"
    lock.write_text(json.dumps({"owner": "t", "token": "x", "created_at": "yesterday"}))
    r = run("lock", "status", lock)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"held": True, "owner": "t", "age_seconds": 0}
