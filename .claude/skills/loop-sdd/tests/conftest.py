import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin"


@pytest.fixture
def run():
    def _run(name, *args, input=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(BIN / f"{name}.py"), *map(str, args)],
            input=input, text=True, capture_output=True, cwd=cwd,
        )
    return _run


@pytest.fixture
def good_config():
    return {
        "check_command": ["python3", "-m", "pytest", "-q"],
        "allowed_paths": ["src/", "tests/"],
        "max_attempts_per_task": 3,
        "max_elapsed_seconds_per_tick": 600,
        "no_progress_limit": 2,
        "fix_rounds_max": 3,
        "routing": {"policy": "balance", "switch_at": 85, "stale_after_seconds": 3600},
        "seats": {
            "implementer": {"backend": "claude", "fallback": "codex", "model": "sonnet", "codex_model": "gpt-5.4"},
            "reviewer": {"backend": "codex", "fallback": "claude", "model": "opus", "codex_model": "gpt-5.4"},
            "re_reviewer": {"backend": "codex", "fallback": "claude", "model": "sonnet", "codex_model": "gpt-5.4"},
        },
    }
