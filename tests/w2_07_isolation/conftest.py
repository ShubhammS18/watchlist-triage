"""Shared fixtures of the W2-07 tests.

The proofs that need a private network namespace (`unshare -rnm`, which needs Linux with unprivileged user
namespaces) always run. Where that is not available they fail with a message saying so; there is no way to skip
them, so the gate cannot pass without them.
"""
import subprocess

import pytest


@pytest.fixture(scope="session")
def netns():
    """Fail unless `unshare -rnm` works here and the loopback device can be brought up inside it."""
    try:
        done = subprocess.run(["unshare", "-rnm", "ip", "link", "set", "lo", "up"], capture_output=True, text=True,
                              timeout=30)
        problem = (done.stderr.strip() or f"exit status {done.returncode}") if done.returncode else None
    except FileNotFoundError:
        problem = "unshare is not installed"
    except subprocess.TimeoutExpired:
        problem = "it did not finish in 30 seconds"
    if problem:
        pytest.fail(f"zero-query proof cannot run: `unshare -rnm ip link set lo up` failed here ({problem}). It needs "
                    f"Linux with unprivileged user namespaces and the `ip` command.", pytrace=False)
