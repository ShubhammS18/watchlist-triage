"""Shared fixtures of the W2-07 tests.

The proofs that need a private network namespace (`unshare -rnm`, which needs Linux with unprivileged user
namespaces) run by default. Where that is not available they fail with a message saying so, so the gate cannot
pass without them. Setting WT_SKIP_NETNS=1 skips them instead, with a message saying the proof did not run.
"""
import os
import subprocess

import pytest

SKIP_VARIABLE = "WT_SKIP_NETNS"


@pytest.fixture(scope="session")
def netns():
    """Skip when WT_SKIP_NETNS=1; otherwise fail unless `unshare -rnm` works here."""
    if os.environ.get(SKIP_VARIABLE) == "1":
        pytest.skip(f"zero-query proof did not run: {SKIP_VARIABLE}=1")
    try:
        done = subprocess.run(["unshare", "-rnm", "true"], capture_output=True, text=True, timeout=30)
        problem = done.stderr.strip() if done.returncode else None
    except FileNotFoundError:
        problem = "unshare is not installed"
    if problem:
        pytest.fail(f"zero-query proof cannot run: `unshare -rnm` is not available here ({problem}). It needs Linux "
                    f"with unprivileged user namespaces. Set {SKIP_VARIABLE}=1 to skip it; the proof then does not "
                    f"run.", pytrace=False)
