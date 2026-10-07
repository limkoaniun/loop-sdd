# loop-sdd portable: loop.json generator and installer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any project adopt loop-sdd: `init` writes a starter `loop.json` for the detected stack, the skill no longer hardcodes its own install path, and an installer puts it in `~/.claude/skills` or a project.

**Architecture:** A `loopcfg.py init` subcommand detects the stack from marker files and writes a validated starter config; a new `check_fail_exits` key lets non-pytest runners (cargo exits 101) map to FAIL. The three action files and seat adapters refer to `$SKILL`, resolved by the controller as the directory holding `SKILL.md`. `install.sh` symlinks (user) or copies (project).

**Tech Stack:** Python 3.11+ standard library, bash, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-loop-sdd-design.md` (Amendments section) plus the in-chat design approved 2026-10-08: stack detection table, `check_fail_exits`, `$SKILL`, `install.sh` modes.

## Global Constraints

- Helpers stay standard-library only; exit 2 with `error:` on bad input.
- `loopcfg.py init [DIR]` never overwrites an existing `loop.json` (exit 0, prints `{"written": false, "reason": "exists"}`).
- Detection table, exactly: `pyproject.toml` or `pytest.ini` or `setup.cfg` → `["python3", "-m", "pytest", "-q"]`, marker `passed|failed|error`, fail exits `[1]`, allowed `["src/", "tests/"]`; `Cargo.toml` → `["cargo", "test"]`, marker `test result:`, fail exits `[101]`, allowed `["src/", "tests/"]`; `package.json` → `["npm", "test"]`, marker `Tests:|passing|failing`, fail exits `[1]`, allowed `["src/", "test/"]`; `go.mod` → `["go", "test", "./..."]`, marker `^ok|FAIL`, fail exits `[1]`, allowed `["."]` is NOT allowed (it would cover tasks/), so use `["cmd/", "internal/", "pkg/"]`; none → `["REPLACE_ME"]`, marker `REPLACE_ME`, fail exits `[1]`, allowed `["src/"]`. Precedence when several markers exist: Python, Rust, Node, Go.
- `check_fail_exits`: optional list of distinct ints in 1..255, default `[1]`; validated by `loopcfg.py validate`.
- Written starter must pass `loopcfg.py validate` for every detected stack; the unknown-stack starter must FAIL validation (so a user cannot run it unedited). Therefore validation rejects a `check_command` whose first element is `REPLACE_ME`.
- The structural test keeps pinning helper names in tick.md; path prefixes change to `$SKILL/bin/`.
- Commit subjects conventional, no co-author trailer. Both suites green before each commit: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests -q` and `.venv/bin/python -m pytest -q`.

## Review Focus

1. A project with both `pyproject.toml` and `package.json` (a Python service with a JS front end). Expected: Python wins by the stated precedence and the file says so in a `"_detected"` note. Test in Task 1.
2. `cargo test` exiting 101 on failures. Expected: tick.md maps 101 to FAIL only because `check_fail_exits` lists it; exit 1 from cargo (build error) is UNKNOWN. Covered by tick.md wording in Task 1 and the structural test.
3. `install.sh --user` when `~/.claude/skills/loop-sdd` already exists as a real directory. Expected: refuse with a message, never delete it. Test in Task 2.
4. `install.sh /path` when the path is not a git repository root. Expected: still copies (the skill does not require git at install time) but prints a warning. Test in Task 2.
5. A controller reading `$SKILL` when the skill is installed user-level: `tick.md` must never assume `.claude/skills/loop-sdd` exists in the project. Pinned by a test in Task 2 that greps for the literal path in the actions and seats.

---

### Task 1: `loopcfg.py init`, `check_fail_exits`, and the exit mapping

**Files:**
- Modify: `.claude/skills/loop-sdd/bin/loopcfg.py`
- Modify: `.claude/skills/loop-sdd/actions/tick.md` (step 4 mapping)
- Modify: `.claude/skills/loop-sdd/actions/init.md` (step 0 and step 2 mapping)
- Modify: `loop.json` (add `"check_fail_exits": [1]`)
- Modify: `.claude/skills/loop-sdd/tests/test_skill_docs.py` (pin `check_fail_exits`)
- Test: `.claude/skills/loop-sdd/tests/test_loopcfg.py` (append)

**Interfaces:**
- Produces: `loopcfg.py init [DIR]` → writes `DIR/loop.json`, prints `{"written": true, "path": ..., "stack": "python|rust|node|go|unknown"}`; exit 0. Existing file → `{"written": false, "reason": "exists", "path": ...}`, exit 0. DIR missing → exit 2.
- Produces: config key `check_fail_exits` (list of ints) consumed by tick.md step 4 and init.md step 2.

- [ ] **Step 1: Write the failing tests** (append to `test_loopcfg.py`)

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests/test_loopcfg.py -q`
Expected: 8 new tests fail (usage error on `init`; missing key check).

- [ ] **Step 3: Implement in loopcfg.py**

Replace the module docstring's first line with `"""Validate or generate loop.json. Usage: loopcfg.py validate PATH | loopcfg.py init [DIR]` and keep the marker paragraph. Add after `LIMITS`:

```python
STACKS = (
    # name, marker files, check_command, check_ran_marker, check_fail_exits, allowed_paths
    ("python", ("pyproject.toml", "pytest.ini", "setup.cfg"), ["python3", "-m", "pytest", "-q"], "passed|failed|error", [1], ["src/", "tests/"]),
    ("rust", ("Cargo.toml",), ["cargo", "test"], "test result:", [101], ["src/", "tests/"]),
    ("node", ("package.json",), ["npm", "test"], "Tests:|passing|failing", [1], ["src/", "test/"]),
    ("go", ("go.mod",), ["go", "test", "./..."], "^ok|FAIL", [1], ["cmd/", "internal/", "pkg/"]),
)
UNKNOWN = ("unknown", (), ["REPLACE_ME"], "REPLACE_ME", [1], ["src/"])
DEFAULT_SEATS = {
    "implementer": {"backend": "claude", "fallback": "codex", "model": "sonnet", "codex_model": "gpt-5.4"},
    "reviewer": {"backend": "codex", "fallback": "claude", "model": "opus", "codex_model": "gpt-5.4"},
    "re_reviewer": {"backend": "codex", "fallback": "claude", "model": "sonnet", "codex_model": "gpt-5.4"},
}


def detect(directory: Path):
    found = [s for s in STACKS if any((directory / m).exists() for m in s[1])]
    return (found[0], [s[0] for s in found]) if found else (UNKNOWN, [])


def starter(directory: Path) -> tuple[dict, str]:
    (name, _, command, marker, fail_exits, allowed), all_found = detect(directory)
    note = f"detected {name}" + (f" (also saw: {', '.join(all_found[1:])}; python > rust > node > go)" if len(all_found) > 1 else "")
    if name == "unknown":
        note = "no stack marker found; replace check_command, check_ran_marker, check_fail_exits and allowed_paths before running"
    cfg = {
        "_detected": note,
        "check_command": command,
        "check_ran_marker": marker,
        "check_fail_exits": fail_exits,
        "allowed_paths": allowed,
        "max_attempts_per_task": 3,
        "max_elapsed_seconds_per_tick": 600,
        "no_progress_limit": 2,
        "fix_rounds_max": 3,
        "routing": {"policy": "balance", "switch_at": 85, "stale_after_seconds": 3600},
        "seats": DEFAULT_SEATS,
    }
    return cfg, name


def cmd_init(directory: Path) -> int:
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    path = directory / "loop.json"
    if path.exists():
        print(json.dumps({"written": False, "reason": "exists", "path": str(path)}))
        return 0
    cfg, name = starter(directory)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": True, "path": str(path), "stack": name}))
    return 0
```

In `validate`, after the `check_command`/`allowed_paths` loop add:

```python
    if string_list(cfg.get("check_command")) and cfg["check_command"][0] == "REPLACE_ME":
        errors.append("check_command is the REPLACE_ME placeholder; edit loop.json before running")
    if "check_fail_exits" in cfg:
        fe = cfg["check_fail_exits"]
        if (
            not isinstance(fe, list) or not fe
            or any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 255 for v in fe)
            or len(set(fe)) != len(fe)
        ):
            errors.append("check_fail_exits must be a non-empty list of distinct integers in 1..255 (default [1])")
```

Replace `main` with:

```python
def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "validate":
        try:
            cfg = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"error: cannot read config: {error}", file=sys.stderr)
            return 2
        errors = validate(cfg)
        if errors:
            for e in errors:
                print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps({"ok": True}))
        return 0
    if 1 <= len(argv) <= 2 and argv[0] == "init":
        return cmd_init(Path(argv[1]) if len(argv) == 2 else Path("."))
    print("usage: loopcfg.py validate PATH | loopcfg.py init [DIR]", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Wire the mapping into tick.md and init.md**

tick.md step 4 ("Fresh check"): replace the three mapping bullets with:

```markdown
- exit 0 → `PASS`;
- exit in `check_fail_exits` (from `loop.json`, default `[1]`) AND the captured
  tail matches `check_ran_marker` → `FAIL` (the tests ran and some failed);
- anything else, including a listed exit without a marker match (runner
  missing, collection error) → `UNKNOWN`, reason "check did not run: <last
  stderr line>".
```

init.md: insert a new first step before the validate step and renumber:

```markdown
1. `python3 $SKILL/bin/loopcfg.py init .` — writes a starter `loop.json` for the
   detected stack if none exists (never overwrites). If it wrote one, print the
   `_detected` note and tell the user to review `check_command`,
   `allowed_paths`, and the seats before continuing; an unknown stack leaves a
   `REPLACE_ME` placeholder that validation refuses.
```

and in the check step change "Unless the exit is 0 or 1 AND the tail matches the marker" to "Unless the exit is 0, or is listed in `check_fail_exits` (default `[1]`) AND the tail matches the marker".

Note: init.md path prefixes still read `.claude/skills/loop-sdd/bin/` at this point; Task 2 switches them to `$SKILL/bin/`. Use `python3 .claude/skills/loop-sdd/bin/loopcfg.py init .` in this task's wording so it matches the rest of the file; Task 2 rewrites all of them together.

`loop.json`: add `"check_fail_exits": [1],` after `check_ran_marker`.

`test_skill_docs.py`: in `test_tick_references_every_helper_and_template`, add `assert "check_fail_exits" in text`; in `test_init_patches_statusline_and_status_reads_inbox` add `assert "loopcfg.py init" in (SKILL / "actions" / "init.md").read_text()`.

- [ ] **Step 5: Run both suites**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests -q && .venv/bin/python -m pytest -q`
Expected: `92 passed` then `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/loop-sdd loop.json
git commit -m "feat: loopcfg init writes a starter loop.json and check_fail_exits maps runner exits"
```

---

### Task 2: `$SKILL` path, `install.sh`, README install section

**Files:**
- Modify: `.claude/skills/loop-sdd/SKILL.md`
- Modify: `.claude/skills/loop-sdd/actions/init.md`, `tick.md`, `status.md`
- Modify: `.claude/skills/loop-sdd/seats/implementer.md`, `reviewer.md`, `re-reviewer.md`
- Create: `install.sh`
- Modify: `README.md`
- Test: `.claude/skills/loop-sdd/tests/test_install.py`
- Modify: `.claude/skills/loop-sdd/tests/test_skill_docs.py`

**Interfaces:**
- Produces: `install.sh --user` → symlink `~/.claude/skills/loop-sdd` → this repo's skill dir (honours `$HOME`; refuses if the target exists and is not a symlink to us). `install.sh /path/to/project` → copies the skill dir to `/path/to/project/.claude/skills/loop-sdd` (refuses if it exists unless `--force`), warns if `/path/to/project/.git` is missing. Exit 0 on success, 1 on refusal, 2 on usage error. Prints the next commands.
- Produces: `$SKILL` convention: SKILL.md states "`$SKILL` is the directory that contains this SKILL.md; you know it because you just read the file. Every helper is `python3 $SKILL/bin/<name>.py`."

- [ ] **Step 1: Write the failing tests**

`test_install.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests/test_install.py -q`
Expected: 6 failed.

- [ ] **Step 3: Write install.sh**

```bash
#!/usr/bin/env bash
# Install the loop-sdd skill for Claude Code.
#   install.sh --user              symlink into ~/.claude/skills/loop-sdd (all projects)
#   install.sh /path/to/project    copy into <project>/.claude/skills/loop-sdd
#   add --force to replace an existing project copy
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/.claude/skills/loop-sdd"
[ -f "$src/SKILL.md" ] || { echo "error: skill not found at $src" >&2; exit 2; }

usage() { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

next_steps() {
  cat <<EOF
Installed. Next:
  cd $1 && claude
  /loop-sdd init      # writes a starter loop.json if missing, validates, checks quota sources
  /loop-sdd status
  /loop 2m /loop-sdd tick
EOF
}

[ $# -ge 1 ] || usage
force=0
target=""
for arg in "$@"; do
  case "$arg" in
    --user) target="--user" ;;
    --force) force=1 ;;
    --*) usage ;;
    *) target="$arg" ;;
  esac
done
[ -n "$target" ] || usage

if [ "$target" = "--user" ]; then
  dest="$HOME/.claude/skills/loop-sdd"
  mkdir -p "$(dirname "$dest")"
  if [ -L "$dest" ]; then
    if [ "$(cd "$dest" && pwd -P)" = "$(cd "$src" && pwd -P)" ]; then
      echo "already linked: $dest -> $src"; next_steps "<your project>"; exit 0
    fi
    echo "refused: $dest is a symlink to somewhere else; remove it first" >&2; exit 1
  fi
  if [ -e "$dest" ]; then
    echo "refused: $dest exists and is not a symlink; move it aside first" >&2; exit 1
  fi
  ln -s "$src" "$dest"
  echo "linked: $dest -> $src"
  next_steps "<your project>"
  exit 0
fi

proj="$target"
[ -d "$proj" ] || { echo "error: not a directory: $proj" >&2; exit 2; }
[ -d "$proj/.git" ] || echo "warning: $proj is not a git repository root; the loop needs git when it runs"
dest="$proj/.claude/skills/loop-sdd"
if [ -e "$dest" ] && [ "$force" -ne 1 ]; then
  echo "refused: $dest exists; pass --force to replace it" >&2; exit 1
fi
rm -rf "$dest"
mkdir -p "$dest"
cp -R "$src/SKILL.md" "$src/actions" "$src/seats" "$src/bin" "$dest/"
find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "copied: $dest"
next_steps "$proj"
```

`chmod +x install.sh`.

- [ ] **Step 4: Replace hardcoded paths with `$SKILL`**

SKILL.md: replace the paragraph starting "Everything that must be deterministic is a helper under" with:

```markdown
`$SKILL` is the directory that contains this SKILL.md. You know it because
you just read the file; it may be `.claude/skills/loop-sdd` in the project or
`~/.claude/skills/loop-sdd` for a user-level install. Everything that must be
deterministic is a helper under `$SKILL/bin/`. Run them with
`python3 $SKILL/bin/<name>.py`. Every helper prints JSON on success and
exits 2 on bad input or 3 when it refuses. Trust their output over your own
reading of a file.
```

tick.md lines 6-7: `H=python3 $SKILL/bin` and remove the `SKILL=.claude/skills/loop-sdd` line (replace with `- $SKILL` is the skill directory from SKILL.md; seat templates live at `$SKILL/seats/`). init.md, status.md: `python3 .claude/skills/loop-sdd/bin/` → `python3 $SKILL/bin/`. The three seat adapter `noop` rows: same substitution. Do it with one sed over the seven files and then grep to confirm zero remaining occurrences.

- [ ] **Step 5: README**

Add an `## Install` section after the intro paragraph:

````markdown
## Install

From a clone of this repo:

```bash
./install.sh --user            # one symlink; /loop-sdd works in every project
./install.sh ~/code/myproject  # or copy into one project
```

Then in that project: `claude`, `/loop-sdd init`. Init writes a starter
`loop.json` for the stack it detects (Python, Rust, Node, Go) and refuses to
continue until the file validates. Review `check_command`, `allowed_paths`,
and the seats before the first tick.
````

In "Configuring the loop", add `"check_fail_exits": [1],` to the example, a table row `| check_fail_exits | exit codes that mean "tests ran and failed" (cargo uses 101) |`, a row for `check_ran_marker`, and after the table:

````markdown
A Rust project's generated file differs only in the check:

```json
"check_command": ["cargo", "test"],
"check_ran_marker": "test result:",
"check_fail_exits": [101],
```
````

Replace the Quick start's `git clone ...; cd loop-sdd-lab; claude` block with a pointer to Install, keeping the venv sentence for this lab.

- [ ] **Step 6: Run both suites**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests -q && .venv/bin/python -m pytest -q`
Expected: `98 passed` then `5 passed`.

- [ ] **Step 7: Commit**

```bash
git add install.sh README.md .claude/skills/loop-sdd
git commit -m "feat: installable skill with \$SKILL paths and install.sh"
```

---

### Task 3: `docs/TUTORIAL.md`, a walkthrough for a new project

**Files:**
- Create: `docs/TUTORIAL.md`
- Modify: `README.md` (link in the intro and in Install)
- Test: `.claude/skills/loop-sdd/tests/test_tutorial.py`

**Interfaces:**
- Consumes: `install.sh` modes (Task 2), `loopcfg.py init` behaviour and the detection table (Task 1), the `/loop-sdd init|tick|status` actions, task-file format, `loop.json` keys, the noop dry run, outcomes and inbox semantics as shipped.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOC = ROOT / "docs" / "TUTORIAL.md"

REQUIRED_HEADINGS = [
    "## 1. Install", "## 2. Create loop.json", "## 3. Write your first task", "## 4. Dry run",
    "## 5. First real tick", "## 6. Read what happened", "## 7. When it stops", "## 8. Route work between Claude and Codex",
    "## 9. Stop the loop",
]
REQUIRED_STRINGS = [
    "./install.sh --user", "/loop-sdd init", "/loop-sdd tick", "/loop-sdd status", "/loop 2m /loop-sdd tick",
    "check_fail_exits", "check_ran_marker", "allowed_paths", "seat_overrides", "status: pending", "status: blocked",
    ".loop/inbox.md", ".loop/ledger.md", ".loop/runs/", "noop", "switch_at", "balance", "fixed",
    "PASS", "RETRY", "IDLE", "STOPPED", "UNKNOWN", "REFUSED",
]


def test_tutorial_structure():
    text = DOC.read_text()
    for h in REQUIRED_HEADINGS:
        assert h in text, h
    for s in REQUIRED_STRINGS:
        assert s in text, s
    assert "TUTORIAL.md" in (ROOT / "README.md").read_text()
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests/test_tutorial.py -q`
Expected: FAIL with FileNotFoundError.

- [ ] **Step 3: Write docs/TUTORIAL.md**

Write it for a developer who has never seen this repo. Each numbered section has: what you type, what you should see, and what it means. Use the exact command and file names. Content per section:

1. **Install.** Prerequisites (Claude Code 2.1.80+, Codex CLI logged in and registered as the `codex` MCP server, Python 3.11+, git). `./install.sh --user` vs `./install.sh /path/to/project`, what each does, how to verify (`ls ~/.claude/skills/loop-sdd`).
2. **Create loop.json.** Run `/loop-sdd init` in the project. Show the generated Python example and say which lines to review: `check_command`, `check_ran_marker`, `check_fail_exits`, `allowed_paths`, the seats. One paragraph per key group explaining what breaks if it is wrong. Show the Rust variant (cargo, `test result:`, `[101]`). What init refuses and why (unknown stack `REPLACE_ME`, a check that cannot run, invalid limits).
3. **Write your first task.** `tasks/001-<slug>.md` with the exact frontmatter, a good brief (acceptance criteria that name the test file), why `tasks/` is outside `allowed_paths`, and why only `pending` tasks are picked, in filename order.
4. **Dry run.** Set every seat to `noop`, run `/loop-sdd tick` once, show the expected ledger line, explain that no commit is made and task overrides are ignored, then reset: set the task back to `status: pending`, delete `.loop/`, restore the seats.
5. **First real tick.** `/loop-sdd tick` once by hand, what a `RETRY` means and why it is normal, then `/loop 2m /loop-sdd tick`. Note that the attempt counter lives in the task file.
6. **Read what happened.** `/loop-sdd status`; the inbox first; one ledger line decoded field by field; the run record in `.loop/runs/`; the per-task folder `.loop/sdd/<id>/` (brief, report, review package, reviewer reply, findings, review.json).
7. **When it stops.** The six outcomes and the seven STOPPED reasons in one table each; the human-only transitions (`blocked` → `pending`, never automatic); the exact edit to unblock the common cases (attempts, no_progress, scope, review, seat, quota).
8. **Route work between Claude and Codex.** `balance` vs `fixed`, `switch_at`, where the quota numbers come from (statusline cache, Codex session logs), what `quota-override.json` means, and `seat_overrides` for an A/B on two similar tasks.
9. **Stop the loop.** Stopping `/loop`; what is safe to delete (`.loop/` runtime state) and what is not (`tasks/`, `loop.json`); the lock file and the one case you delete it by hand.

End with a short "Where things are" table mapping file to purpose.

- [ ] **Step 4: Link from README**

In the intro, after the status blockquote, add: `New here? Read [docs/TUTORIAL.md](docs/TUTORIAL.md) for a step-by-step walkthrough.` In the Install section's last paragraph, add `The [tutorial](docs/TUTORIAL.md) walks through the first tick.`

- [ ] **Step 5: Run both suites**

Run: `.venv/bin/python -m pytest .claude/skills/loop-sdd/tests -q && .venv/bin/python -m pytest -q`
Expected: `99 passed` then `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add docs/TUTORIAL.md README.md .claude/skills/loop-sdd/tests/test_tutorial.py
git commit -m "docs: add a step-by-step tutorial for new projects"
```

---

## Self-review

Spec coverage: tutorial → Task 3; generator and detection table → Task 1; `check_fail_exits` and the mapping → Task 1; `$SKILL` → Task 2; installer modes and refusals → Task 2; README → Task 2. Review Focus items 1, 2 → Task 1 tests and wording; 3, 4, 5 → Task 2 tests. Placeholders: none. Type consistency: `cmd_init` output keys match the tests; `check_fail_exits` name is identical in loopcfg, loop.json, tick.md, init.md, README.
