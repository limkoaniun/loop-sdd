import json


def reading(five, seven, age=10):
    return {"five_hour": five, "seven_day": seven, "age_seconds": age, "source": "t",
            "resets_at": {"five_hour": 1, "seven_day": 2}}


def choose(run, tmp_path, good_config, readings, seat="implementer", override=None, policy="balance", now=1000, seat_overrides=None):
    good_config["routing"]["policy"] = policy
    cfg = tmp_path / "loop.json"; cfg.write_text(json.dumps(good_config))
    rd = tmp_path / "r.json"; rd.write_text(json.dumps(readings))
    args = ["quota", "choose", "--readings", rd, "--config", cfg, "--seat", seat, "--now", now]
    if override is not None:
        ov = tmp_path / "ov.json"; ov.write_text(json.dumps(override)); args += ["--override", ov]
    if seat_overrides is not None:
        args += ["--seat-overrides", json.dumps(seat_overrides)]
    r = run(*args)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_balance_picks_lower_weekly(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(20, 60), "codex": reading(5, 30)})
    assert out["backend"] == "codex" and out["blind"] is False


def test_balance_skips_side_over_switch_at(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(90, 10), "codex": reading(5, 70)})
    assert out["backend"] == "codex"


def test_both_over_is_quota(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(90, 10), "codex": reading(5, 86)})
    assert out["backend"] is None and out["reason"] == "quota"


def test_both_overridden_is_quota_never_blind(run, tmp_path, good_config):
    ov = {"claude": {"resets_at": 5000}, "codex": {"resets_at": 5000}}
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": None}, override=ov, policy="fixed")
    assert out["backend"] is None and out["reason"] == "quota" and out["blind"] is False


def test_expired_override_is_ignored(run, tmp_path, good_config):
    ov = {"codex": {"resets_at": 500}}
    out = choose(run, tmp_path, good_config, {"claude": reading(20, 60), "codex": reading(5, 30)}, override=ov)
    assert out["backend"] == "codex"


def test_fixed_uses_backend_blind_when_unknown(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": reading(5, 30)}, policy="fixed")
    assert out["backend"] == "claude" and out["blind"] is True


def test_fixed_falls_back_when_backend_over(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(86, 10), "codex": reading(5, 30)}, policy="fixed")
    assert out["backend"] == "codex" and out["blind"] is False


def test_stale_reading_is_unknown(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(1, 1, age=99999), "codex": reading(5, 30)})
    assert out["backend"] == "codex"


def test_seat_overrides_merge(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(1, 1), "codex": reading(1, 1)},
                 policy="fixed", seat_overrides={"implementer": {"backend": "codex", "fallback": "claude"}})
    assert out["backend"] == "codex"


def test_noop_seat(run, tmp_path, good_config):
    good_config["seats"]["implementer"] = {"backend": "noop", "fallback": "noop", "model": "x", "codex_model": "x"}
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": None})
    assert out["backend"] == "noop"


def test_malformed_override_entry_excludes_backend(run, tmp_path, good_config):
    ov = {"claude": 5000}
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": reading(5, 30)}, override=ov, policy="fixed")
    assert out["backend"] == "codex" and out["blind"] is False


def test_string_resets_at_excludes_backend(run, tmp_path, good_config):
    ov = {"claude": {"resets_at": "5000"}, "codex": {"resets_at": None}}
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": None}, override=ov, policy="fixed")
    assert out["backend"] is None and out["reason"] == "quota"


def test_wrong_shape_inputs_exit_2(run, tmp_path, good_config):
    cfg = tmp_path / "loop.json"; cfg.write_text(json.dumps(good_config))
    rd = tmp_path / "r.json"; rd.write_text("[]")
    r = run("quota", "choose", "--readings", rd, "--config", cfg, "--seat", "implementer")
    assert r.returncode == 2 and "error:" in r.stderr
    rd.write_text(json.dumps({"claude": None, "codex": None}))
    r = run("quota", "choose", "--readings", rd, "--config", cfg, "--seat", "implementer", "--seat-overrides", "[1]")
    assert r.returncode == 2 and "error:" in r.stderr
    r = run("quota", "choose", "--readings", rd, "--config", cfg, "--seat", "nobody")
    assert r.returncode == 2 and "error:" in r.stderr


def test_balance_tie_goes_to_backend(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": reading(1, 30), "codex": reading(1, 30)})
    assert out["backend"] == "claude"


def test_balance_with_nothing_fresh_is_quota(run, tmp_path, good_config):
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": None})
    assert out["backend"] is None and out["reason"] == "quota" and out["blind"] is False


def test_noop_config_ignores_task_overrides(run, tmp_path, good_config):
    good_config["seats"]["implementer"] = {"backend": "noop", "fallback": "noop", "model": "x", "codex_model": "x"}
    out = choose(run, tmp_path, good_config, {"claude": None, "codex": None},
                 seat_overrides={"implementer": {"backend": "codex", "fallback": "claude"}})
    assert out["backend"] == "noop"
