def test_implementer_writes_report_and_reports_done(run, tmp_path):
    report = tmp_path / "report.md"
    r = run("noop", "implementer", "--report", report)
    assert r.returncode == 0, r.stderr
    assert report.exists() and "noop" in report.read_text()
    assert "Status: DONE" in r.stdout and str(report) in r.stdout


def test_reviewer_approves(run):
    r = run("noop", "reviewer")
    assert r.stdout.splitlines()[0] == "Verdict: APPROVED"


def test_re_reviewer_addressed(run):
    r = run("noop", "re-reviewer")
    assert r.stdout.splitlines()[0] == "Verdict: ADDRESSED"
