"""W2-02: a known limit, documented, not fixed (DEC-W2-02-MODEL-READING-RISK). The model's NO_LINK is trusted: on public
bundles whose notes claim the customer is the listed person, a wrong NO_LINK still gives CLOSE, with no system failure.
The rubric says these must escalate; the control is human review of every close. This test pins the behaviour so a
change to it is seen. It runs the real child process with a scripted model, on the frozen world's public files only."""
import json

import pytest

from baseline_agent.payload import build_payload
from model_interface import Settings
from model_interface.stub import Stub
from triage_agent.recommend import recommend
from triage_agent.rules import decide
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

SETTINGS = Settings(model="stub-1", temperature=0, max_tokens=512, timeout_s=30)
BUNDLES = {one["id"]: one["evidence"] for one in [*load_alerts(), *load_twins()]}
NO_LINK = json.dumps({"schema_version": "1", "answer": "NO_LINK", "reason": "Scripted wrong answer.", "note_ids": []})


@pytest.mark.parametrize("item", ["ALT-0327", "ALT-0524", "TWN-11"])
def test_known_limit_a_wrong_no_link_on_a_note_claiming_identity_recommends_close(item):
    evidence = BUNDLES[item]
    assert decide(build_payload(evidence)["items"]) is None  # the model is asked
    assert any(e["kind"] == "snippet" and "is the same person as" in e["value"] for e in evidence)
    result = recommend(evidence, Stub(replies=[NO_LINK]), SETTINGS, sink=[], retries=2, correlation_id=f"{item}/1")
    assert result["recommendation"] == "CLOSE" and not result["system_failure"]
