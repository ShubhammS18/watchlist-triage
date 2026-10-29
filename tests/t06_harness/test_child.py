"""T06 stage 5: what is only shown through the real agent process. The file-system recorder with its positive
control (DEC-T06-NO-FILES), the three failure kinds only the parent builds, and the child timeout with the
margin patched for the test (DEC-T06-MARGIN-PATCH). Claim of the recorder: tested on a sample, not enforced
per item.
"""
import copy
import os
import threading
import time
from pathlib import Path

import pytest

import fake_model
import recording_agent
from baseline_agent import recommend as baseline_recommend
from conftest import FIXTURES
from framings import FRAMINGS, frame
from harness import cost as money
from harness import run as harness_run
from harness import score
from model_interface import Result, Settings, providers
from worldgen.loader import load_alerts

PRICES = {"kind": "fixture", "source": "fixture", "date": "2026-10-13", "currency": "USD", "unit": "per million tokens",
          "models": {"fake-1": {"input": "1.00", "output": "2.00"}}}
RECORDED = "tests.t06_harness.recording_agent"
CONTROL = "tests.t06_harness.recording_agent_control"


def sample():
    """One alert for every outcome of the fake, in all three framings: 36 items."""
    chosen = {}
    for alert in load_alerts():
        chosen.setdefault(fake_model.outcome_of([item["id"] for item in alert["evidence"]]), alert)
    return [{"item_id": f"{alert['id']}/{framing}", "alert_id": alert["id"], "framing": framing, "twin": False,
             "evidence": frame(alert, framing)} for alert in chosen.values() for framing in FRAMINGS]


def without_timings(line):
    line = copy.deepcopy(line)
    del line["wall_s"], line["queue_s"]
    line["result"]["log"]["latency_s"] = None
    for attempt in line["result"]["log"]["attempt_log"]:
        attempt["latency_s"] = None
    return line


def by_id(lines):
    return sorted((without_timings(line) for line in lines), key=lambda line: line["item_id"])


# ---- the recorder

def test_the_agent_opens_no_file_and_lists_no_directory_on_the_sample(monkeypatch):
    items = sample()
    model, settings = providers.load(FIXTURES.joinpath("model_fake.json"))
    plain, recorded = [], []
    harness_run.hand_off(items, fake_model.inprocess, model, settings, plain)
    monkeypatch.setattr(baseline_recommend, "MODULE", RECORDED)
    harness_run.hand_off(items, harness_run.AGENTS["baseline"], model, settings, recorded, workers=4)
    assert len(recorded) == 36 and not [line["item_id"] for line in recorded if line["result"]["failure_kind"] == "child_crash"]
    assert by_id(recorded) == by_id(plain)  # under the recorder every item comes back exactly as without it
    kinds = {line["result"]["failure_kind"] for line in recorded}
    assert {None, "timeout", "provider_error", "model_refusal", "malformed_output", "missing_citations",
            "unknown_schema_version", "invalid_citation"} == kinds  # replies and every fault path of the sample


def test_positive_control_an_agent_that_opens_a_file_is_caught_on_every_call(monkeypatch):
    items = sample()[:9]
    model, settings = providers.load(FIXTURES.joinpath("model_fake.json"))
    monkeypatch.setattr(baseline_recommend, "MODULE", CONTROL)
    caught = []
    harness_run.hand_off(items, harness_run.AGENTS["baseline"], model, settings, caught, workers=3)
    assert [line["result"]["failure_kind"] for line in caught] == ["child_crash"] * 9
    assert all(line["result"]["log"]["error_name"] == "ChildError" and line["result"]["recommendation"] == "ESCALATE"
               for line in caught)


@pytest.mark.parametrize("touch", [
    lambda: open(__file__, encoding="utf-8").close(),
    lambda: Path(__file__).read_bytes(),
    lambda: os.listdir(Path(__file__).parent),
    lambda: list(os.scandir(Path(__file__).parent)),
    lambda: list(Path(__file__).parent.iterdir()),
    lambda: os.open(__file__, os.O_RDONLY),
])
def test_the_recorder_itself_catches_opens_and_directory_listings(touch):
    with pytest.raises(RuntimeError, match="the agent used the file system"):
        recording_agent.watched(touch)
    assert recording_agent.watched(lambda: 1 + 1) == 2 and not recording_agent.armed  # and nothing else
    open(__file__, encoding="utf-8").close()  # unarmed, it notes nothing
    assert recording_agent.watched(lambda: "quiet") == "quiet"


def test_the_recorder_is_test_only_and_the_shipped_agent_module_is_unchanged():
    assert baseline_recommend.MODULE == "baseline_agent.agent"
    assert not list(harness_run.records.REPO.joinpath("harness").glob("*record*"))


# ---- the three failure kinds only the parent builds, through the real child

def one_item():
    alert = load_alerts()[0]
    return [{"item_id": f"{alert['id']}/1", "alert_id": alert["id"], "framing": 1, "twin": False, "evidence": frame(alert, 1)}]


def through_the_child(model, settings=Settings("fake-1", 0, 512, 30)):
    done = []
    harness_run.hand_off(one_item(), harness_run.AGENTS["baseline"], model, settings, done)
    return done[0]


def assert_parent_built(line, kind, error_name):
    result = line["result"]
    assert result["failure_kind"] == kind and result["system_failure"] is True and result["recommendation"] == "ESCALATE"
    assert result["cited_ids"] == [] and result["log"]["error_name"] == error_name and result["log"]["attempts"] is None
    assert kind not in harness_run.TRANSIENT and score.verdict(line) == "ESCALATE"  # an ordinary failure, not transient


def plain(attempts):
    """The attempt records without the prompt size that W2-02 added to each."""
    return [{key: value for key, value in attempt.items() if key != "prompt_bytes"} for attempt in attempts]


def test_the_real_margin_is_ten_seconds():
    assert baseline_recommend.MARGIN_S == 10


def test_a_child_timeout_is_fast_with_the_margin_patched_and_its_unfinished_call_is_counted(monkeypatch):
    monkeypatch.setattr(baseline_recommend, "MARGIN_S", 0.2)  # in this process only; the shipped value is pinned above
    begun = time.monotonic()
    line = through_the_child(fake_model.Slow(delay=2.5), Settings("fake-1", 0, 512, 0.1))  # limit: 3 x 0.1 + 0.2 s
    assert time.monotonic() - begun < 2.0  # not the 10 seconds of the real margin
    assert_parent_built(line, "child_timeout", "ChildTimeout")
    # the model call had started and had not returned: it is counted, without token counts
    assert plain(line["attempts"]) == [{"error": "Unfinished", "input_tokens": None, "output_tokens": None, "model_id": None}]
    assert line["attempts"][0]["prompt_bytes"] > 0  # noted when the call started (W2-02)
    block = money.cost(line["attempts"], PRICES)
    assert block["at_least"] is True and block["attempts_without_token_counts"] == 1
    assert block["statement"] == "at least 0 USD; 1 attempts without token counts"


def test_a_child_whose_result_the_parent_refuses_is_a_child_crash():
    line = through_the_child(lambda request: Result("not json", 123, 1, 1, 0.0))  # a model id that is not text
    assert_parent_built(line, "child_crash", "BadResult")
    assert plain(line["attempts"]) == [{"error": None, "input_tokens": 1, "output_tokens": 1, "model_id": 123}]


def test_a_fault_inside_the_model_object_is_an_internal_error():
    def broken(request):
        raise RuntimeError("the model object itself broke")

    line = through_the_child(broken)
    assert_parent_built(line, "internal_error", "RuntimeError")
    assert plain(line["attempts"]) == [{"error": "RuntimeError", "input_tokens": None, "output_tokens": None, "model_id": None}]


def test_the_parent_built_kinds_are_scored_as_escalations_and_never_as_transient():
    from worldgen.truth import load_truth
    item = one_item()[0]
    lines = []
    for kind in ("child_timeout", "child_crash", "internal_error"):
        lines.append({**item, "sent_ids": [one["id"] for one in item["evidence"]], "wall_s": 1.0, "attempts": [],
                      "item_id": f"{item['alert_id']}/{len(lines) + 1}", "framing": len(lines) + 1,
                      "result": {"recommendation": "ESCALATE", "reason": f"System failure: {kind}", "cited_ids": [],
                                 "system_failure": True, "failure_kind": kind, "citation_invalid": False,
                                 "log": {"latency_s": 1.0}}})
    cell = score.cell(lines, load_truth())
    assert cell["verdicts"] == {"CLOSE": 0, "ESCALATE": 3} and cell["failures"] == 3
    assert [cell["failures_by_kind"][kind] for kind in ("child_timeout", "child_crash", "internal_error")] == [1, 1, 1]
    assert cell["missed_true_matches"] == 0 and cell["verdict_consistency"] == score.rate(1, 1)
    assert harness_run.infra_invalid(sum(line["result"]["failure_kind"] in harness_run.TRANSIENT for line in lines), 3, "0") is False


# ---- a call that is still under way when its item returns

def test_a_call_is_noted_when_it_starts_and_an_item_keeps_its_own_snapshot():
    release, entered = threading.Event(), threading.Event()

    def model(request):
        entered.set()
        release.wait(5)
        return Result("late", "fake-1", 7, 3, 0.0)

    tokens = harness_run.Tokens(model)
    worker = threading.Thread(target=tokens, args=("request",))
    worker.start()
    assert entered.wait(5)
    kept = tokens.snapshot()  # what the item keeps when it returns while the call is under way
    assert kept == [{"error": "Unfinished", "input_tokens": None, "output_tokens": None, "model_id": None,
                     "prompt_bytes": None}]  # a request with no messages has no size (W2-02)
    assert harness_run._calls(kept) == {"attempts": 1, "without_token_counts": 1, "input_tokens": 0, "output_tokens": 0}
    assert money.cost(kept, PRICES)["at_least"] is True  # unknown, and never a cost of 0 that looks complete
    release.set()
    worker.join(5)
    assert tokens.attempts == [{"error": None, "input_tokens": 7, "output_tokens": 3, "model_id": "fake-1", "prompt_bytes": None}]
    assert kept == [{"error": "Unfinished", "input_tokens": None, "output_tokens": None, "model_id": None,
                     "prompt_bytes": None}]  # unchanged
