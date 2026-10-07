import json


def write(tmp_path, cfg):
    p = tmp_path / "loop.json"
    p.write_text(json.dumps(cfg))
    return p


def test_valid_config_ok(run, tmp_path, good_config):
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"ok": True}


def test_zero_limit_refused(run, tmp_path, good_config):
    good_config["max_attempts_per_task"] = 0
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    assert "max_attempts_per_task" in r.stderr


def test_bool_limit_refused(run, tmp_path, good_config):
    good_config["no_progress_limit"] = True
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    assert "no_progress_limit" in r.stderr


def test_same_backend_and_fallback_refused(run, tmp_path, good_config):
    good_config["seats"]["reviewer"]["fallback"] = "codex"
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    assert "reviewer" in r.stderr


def test_noop_requires_noop_fallback(run, tmp_path, good_config):
    good_config["seats"]["implementer"] = {"backend": "noop", "fallback": "claude", "model": "x", "codex_model": "x"}
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    good_config["seats"]["implementer"]["fallback"] = "noop"
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 0, r.stderr


def test_absolute_allowed_path_refused(run, tmp_path, good_config):
    good_config["allowed_paths"] = ["/etc"]
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    assert "allowed_paths" in r.stderr


def test_bad_policy_and_switch_at(run, tmp_path, good_config):
    good_config["routing"]["policy"] = "random"
    good_config["routing"]["switch_at"] = 0
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2
    assert "policy" in r.stderr and "switch_at" in r.stderr


def test_malformed_json(run, tmp_path):
    p = tmp_path / "loop.json"
    p.write_text("{")
    r = run("loopcfg", "validate", p)
    assert r.returncode == 2
