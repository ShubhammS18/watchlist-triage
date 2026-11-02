"""Fixtures of the W2-10 tests: W2-08's test candidate agent registered for the session, with one more test-only
behaviour (model refusals, for the refusal stop rule), a check that no test writes inside the repository, and the
practice world made once."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.joinpath("w2_08_release_protocol")))
sys.path.insert(0, str(HERE))
import release_common as rc  # noqa: E402

from harness import agents  # noqa: E402
from harness import run as harness_run  # noqa: E402


def candidate(items, model, settings, item_id):
    """W2-08's candidate, which may also answer a quarter of the plain clear false positives with a model refusal,
    escalated as a system failure, as the agent does."""
    b = rc.BEHAVIOUR
    facts = b["truth"][item_id.split("/")[0]]
    plain = facts["label"] == "CLEAR_FALSE_POSITIVE" and facts["twin"] is None and facts["twin_of"] is None
    if b.get("refusals") and plain and int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % 4 == 0:
        result, sink = agents._answer("ESCALATE", items, item_id)
        result.update(system_failure=True, failure_kind="model_refusal", cited_ids=[], reason="Test refusal.")
        result["log"] = sink[0] = {**result["log"], "kind": "model_refusal"}
        return result, sink
    return rc.candidate(items, model, settings, item_id)


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(harness_run.AGENTS, "candidate", candidate)
        patch.setattr(harness_run, "MODEL_FREE", (*harness_run.MODEL_FREE, "candidate"))
        yield


@pytest.fixture(scope="session", autouse=True)
def repository_untouched():
    """No test writes inside the repository."""
    status = lambda: subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=rc.REPO,
                                    capture_output=True, text=True).stdout
    before = status()
    yield
    assert status() == before


@pytest.fixture(scope="session")
def practice(tmp_path_factory):
    import made_up
    return made_up.practice_world(tmp_path_factory.mktemp("practice"))
