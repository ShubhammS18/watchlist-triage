"""Shared by the W2-04 tests: the one command the workflow and the gate run, the drift script loaded as a module, and
a way to run it in a folder."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = "tools/check_world_drift.py"
COMMAND = f"python3 {SCRIPT}"            # the workflow's run line must be exactly this
WORKFLOWS = REPO.joinpath(".github", "workflows")

_spec = importlib.util.spec_from_file_location("check_world_drift", REPO.joinpath(SCRIPT))
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


def environment():
    return {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}


def run_script(folder):
    """COMMAND run in `folder` by this interpreter (the venv's Python 3.12, as `python3` is on the runner)."""
    return subprocess.run([sys.executable, "-B", *COMMAND.split()[1:]], cwd=folder,
                          capture_output=True, text=True, env=environment())
