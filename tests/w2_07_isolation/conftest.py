"""Shared fixtures of the W2-07 tests.

The proofs that need a private network namespace (`unshare -rnm`, which needs Linux with unprivileged user
namespaces) always run. Where that is not available they fail with a message saying so; there is no way to skip
them, so the gate cannot pass without them.
"""
import subprocess

import pytest


@pytest.fixture(scope="session")
def netns():
    """Fail unless `unshare -rnm` works here."""
    try:
        done = subprocess.run(["unshare", "-rnm", "true"], capture_output=True, text=True, timeout=30)
        problem = (done.stderr.strip() or f"exit status {done.returncode}") if done.returncode else None
    except FileNotFoundError:
        problem = "unshare is not installed"
    except subprocess.TimeoutExpired:
        problem = "it did not finish in 30 seconds"
    if problem:
        pytest.fail(f"zero-query proof cannot run: `unshare -rnm` is not available here ({problem}). It needs Linux "
                    f"with unprivileged user namespaces.", pytrace=False)
