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


def test_bad_check_ran_marker_refused(run, tmp_path, good_config):
    good_config["check_ran_marker"] = "("
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2 and "check_ran_marker" in r.stderr
    good_config["check_ran_marker"] = ""
    r = run("loopcfg", "validate", write(tmp_path, good_config))
    assert r.returncode == 2 and "check_ran_marker" in r.stderr
    good_config["check_ran_marker"] = "passed|failed|error"
    assert run("loopcfg", "validate", write(tmp_path, good_config)).returncode == 0


def test_init_python_stack(run, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    r = run("loopcfg", "init", tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["written"] is True and out["stack"] == "python"
    cfg = json.loads((tmp_path / "loop.json").read_text())
    assert cfg["check_command"] == ["python3", "-m", "pytest", "-q"]
    assert cfg["check_fail_exits"] == [1] and cfg["check_ran_marker"] == "passed|failed|error"
    assert cfg["allowed_paths"] == ["src/", "tests/"]
    assert run("loopcfg", "validate", tmp_path / "loop.json").returncode == 0


def test_init_rust_stack(run, tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n")
    out = json.loads(run("loopcfg", "init", tmp_path).stdout)
    cfg = json.loads((tmp_path / "loop.json").read_text())
    assert out["stack"] == "rust" and cfg["check_command"] == ["cargo", "test"]
    assert cfg["check_fail_exits"] == [101] and cfg["check_ran_marker"] == "test result:"
    assert run("loopcfg", "validate", tmp_path / "loop.json").returncode == 0


def test_init_node_and_go(run, tmp_path):
    node = tmp_path / "n"; node.mkdir(); (node / "package.json").write_text("{}")
    assert json.loads(run("loopcfg", "init", node).stdout)["stack"] == "node"
    assert json.loads((node / "loop.json").read_text())["allowed_paths"] == ["src/", "test/"]
    go = tmp_path / "g"; go.mkdir(); (go / "go.mod").write_text("module x\n")
    assert json.loads(run("loopcfg", "init", go).stdout)["stack"] == "go"
    assert json.loads((go / "loop.json").read_text())["check_command"] == ["go", "test", "./..."]
    for d in (node, go):
        assert run("loopcfg", "validate", d / "loop.json").returncode == 0


def test_init_precedence_python_over_node(run, tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "package.json").write_text("{}")
    out = json.loads(run("loopcfg", "init", tmp_path).stdout)
    assert out["stack"] == "python"
    assert "python" in json.loads((tmp_path / "loop.json").read_text())["_detected"]


def test_init_unknown_stack_fails_validation(run, tmp_path):
    out = json.loads(run("loopcfg", "init", tmp_path).stdout)
    assert out["stack"] == "unknown"
    r = run("loopcfg", "validate", tmp_path / "loop.json")
    assert r.returncode == 2 and "REPLACE_ME" in r.stderr


def test_init_never_overwrites(run, tmp_path):
    (tmp_path / "loop.json").write_text("{\"keep\": true}")
    out = json.loads(run("loopcfg", "init", tmp_path).stdout)
    assert out == {"written": False, "reason": "exists", "path": str(tmp_path / "loop.json")}
    assert (tmp_path / "loop.json").read_text() == "{\"keep\": true}"


def test_init_missing_dir_exits_2(run, tmp_path):
    r = run("loopcfg", "init", tmp_path / "nope")
    assert r.returncode == 2 and "error:" in r.stderr


def test_check_fail_exits_validated(run, tmp_path, good_config):
    for bad in ([], [0], [1, 1], ["1"], [256], 1):
        good_config["check_fail_exits"] = bad
        r = run("loopcfg", "validate", write(tmp_path, good_config))
        assert r.returncode == 2 and "check_fail_exits" in r.stderr, bad
    good_config["check_fail_exits"] = [1, 101]
    assert run("loopcfg", "validate", write(tmp_path, good_config)).returncode == 0


def test_check_timeout_seconds_validated(run, tmp_path, good_config):
    for bad in (0, "120", True, -5):
        good_config["check_timeout_seconds"] = bad
        r = run("loopcfg", "validate", write(tmp_path, good_config))
        assert r.returncode == 2 and "check_timeout_seconds" in r.stderr, bad
    good_config["check_timeout_seconds"] = 600
    assert run("loopcfg", "validate", write(tmp_path, good_config)).returncode == 0


def test_check_timeout_seconds_only_in_rust_starter(run, tmp_path):
    rust = tmp_path / "rust"; rust.mkdir(); (rust / "Cargo.toml").write_text("[package]\n")
    py = tmp_path / "py"; py.mkdir(); (py / "pyproject.toml").write_text("")
    run("loopcfg", "init", rust); run("loopcfg", "init", py)
    assert json.loads((rust / "loop.json").read_text())["check_timeout_seconds"] == 600
    assert "check_timeout_seconds" not in json.loads((py / "loop.json").read_text())
