"""Fixtures of the W2-05 tests: T06's fake model registered for the session, a check that no test writes inside the
repository, and one whole fake-model run with its log and checkpoint."""
import json
import subprocess

import pytest

from audit_common import REPO, write_config
from audit_common import fake_model
from harness import audit
from harness import run as harness_run


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        fake_model.register(patch)
        yield


@pytest.fixture(scope="session", autouse=True)
def repository_untouched():
    """No test writes inside the repository."""
    status = lambda: subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO,
                                    capture_output=True, text=True).stdout
    before = status()
    yield
    assert status() == before


@pytest.fixture(scope="session")
def full_run(tmp_path_factory):
    """One whole run with the fake model, and every git command it ran: (run folder, manifest, git commands).
    Read-only: a test that changes a file works on a copy."""
    folder = tmp_path_factory.mktemp("full")
    commands, real = [], harness_run.records.subprocess.run

    def recorded(args, *rest, **options):
        commands.append(list(args))
        return real(args, *rest, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(harness_run.records.subprocess, "run", recorded)
        manifest = harness_run.run(write_config(folder), folder.joinpath("out"))
    assert manifest["state"] == "completed", manifest["aborted"]
    return folder.joinpath("out", manifest["run_id"]), manifest, commands


@pytest.fixture(scope="session")
def log_bytes(full_run):
    return full_run[0].joinpath(audit.LOG).read_bytes()


@pytest.fixture(scope="session")
def trusted(full_run):
    return json.loads(full_run[0].joinpath(audit.CHECKPOINT).read_text(encoding="utf-8"))
