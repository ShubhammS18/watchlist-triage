"""Closing without a written reason is refused by both agents (FR-6, FR-18, AC-11, DEC-W2-06-CHOICES), on the child side
and again on the parent side, and ends as ESCALATE with SYSTEM_FAILURE, never CLOSE. The harness does not refuse one
itself; the agents do. A rule's written reason counts as a reason. The real child process runs with a scripted model."""
import json

import pytest

import baseline_agent.recommend as baseline
import triage_agent.recommend as triage
from baseline_agent.payload import build_payload
from conftest import WORLD, lines_of
from framings import FRAMINGS, frame
from harness.agents import always_close
from model_interface import Settings
from model_interface.stub import Stub
from triage_agent.rules import decide
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

SETTINGS = Settings(model="stub-1", temperature=0, max_tokens=512, timeout_s=30)
# A group C alert: the dates of birth conflict, no decisive identifier agrees, and there are notes to read.
ITEMS = [{"id": "C-name", "kind": "customer_field", "field": "name", "value": "Ana Lopez"},
         {"id": "C-dob", "kind": "customer_field", "field": "date_of_birth", "value": "1970-01-01"},
         {"id": "W-name", "kind": "watchlist_field", "field": "name", "value": "Ana López"},
         {"id": "W-dob", "kind": "watchlist_field", "field": "date_of_birth", "value": "1980-02-02"},
         {"id": "S-1", "kind": "snippet", "field": "snippet", "value": "Routine file note."}]
BUNDLE = [{**item, "as_of_date": "2026-09-30"} for item in ITEMS]
MISSING = object()
NO_REASONS = {"empty": "", "spaces and a line break": "  \n", "missing": MISSING, "not text": ["Because."], "null": None}
LOG = {"kind": "ok", "error_name": None, "attempts": 1, "attempt_log": [{"error_name": None, "latency_s": 0.01}],
       "latency_s": 0.02, "model_id": "stub-1"}


def _with(reply, reason):
    return json.dumps(reply if reason is MISSING else {**reply, "reason": reason})


def refused(result):
    return result["recommendation"] == "ESCALATE" and result["system_failure"] is True and result["cited_ids"] == []


@pytest.mark.parametrize("reason", NO_REASONS.values(), ids=NO_REASONS.keys())
def test_the_baseline_agent_refuses_a_close_with_no_written_reason(reason):
    reply = _with({"schema_version": "1", "recommendation": "CLOSE", "cited_ids": ["C-dob", "W-dob"]}, reason)
    assert refused(baseline.recommend(BUNDLE, Stub(default=reply), SETTINGS, sink=[]))


@pytest.mark.parametrize("reason", NO_REASONS.values(), ids=NO_REASONS.keys())
def test_the_triage_agent_refuses_a_no_link_with_no_written_reason(reason):
    reply = _with({"schema_version": "1", "answer": "NO_LINK", "note_ids": []}, reason)
    assert decide(build_payload(BUNDLE)["items"]) is None  # the model is asked: group C
    assert refused(triage.recommend(BUNDLE, Stub(default=reply), SETTINGS, sink=[]))


def test_with_a_written_reason_both_agents_close():
    """The control: the same replies with a reason close, so the refusals above are about the reason."""
    close = json.dumps({"schema_version": "1", "recommendation": "CLOSE", "reason": "Dates differ.", "cited_ids": ["C-dob"]})
    no_link = json.dumps({"schema_version": "1", "answer": "NO_LINK", "reason": "No note links them.", "note_ids": []})
    assert baseline.recommend(BUNDLE, Stub(default=close), SETTINGS, sink=[])["recommendation"] == "CLOSE"
    assert triage.recommend(BUNDLE, Stub(default=no_link), SETTINGS, sink=[])["recommendation"] == "CLOSE"


@pytest.mark.parametrize("reason", ["", "  \n", None], ids=["empty", "spaces", "null"])
def test_each_parent_refuses_a_forged_child_close_with_no_reason(monkeypatch, reason):
    """The parent is the last place a CLOSE passes through, so it checks again, whatever the child sent. For the triage
    agent this checks the model's reason itself: the CLOSE it builds would carry its own rule text either way."""
    forged = {"recommendation": "CLOSE", "reason": reason, "cited_ids": ["C-dob"], "system_failure": False,
              "failure_kind": None, "citation_invalid": False, "log": dict(LOG)}
    monkeypatch.setattr(baseline, "run_child", lambda *arguments, **options: forged)
    result = baseline.recommend(BUNDLE, Stub(), SETTINGS, sink=[])
    assert refused(result) and result["failure_kind"] == "child_crash" and result["log"]["error_name"] == "BadResult"
    answer = {"answer": "NO_LINK", "reason": reason, "note_ids": [], "log": dict(LOG)}
    monkeypatch.setattr(triage, "run_child", lambda *arguments, **options: answer)
    result = triage.recommend(BUNDLE, Stub(), SETTINGS, sink=[])
    assert refused(result) and result["failure_kind"] == "child_crash" and result["log"]["error_name"] == "BadResult"


def test_each_parent_closes_a_forged_child_answer_with_a_reason(monkeypatch):
    """The control for the forged answers above."""
    forged = {"recommendation": "CLOSE", "reason": "Dates differ.", "cited_ids": ["C-dob"], "system_failure": False,
              "failure_kind": None, "citation_invalid": False, "log": dict(LOG)}
    monkeypatch.setattr(baseline, "run_child", lambda *arguments, **options: forged)
    assert baseline.recommend(BUNDLE, Stub(), SETTINGS, sink=[])["recommendation"] == "CLOSE"
    answer = {"answer": "NO_LINK", "reason": "No note links them.", "note_ids": [], "log": dict(LOG)}
    monkeypatch.setattr(triage, "run_child", lambda *arguments, **options: answer)
    assert triage.recommend(BUNDLE, Stub(), SETTINGS, sink=[])["recommendation"] == "CLOSE"


def test_every_close_the_triage_rules_give_on_the_frozen_world_has_a_written_reason():
    agent = WORLD.joinpath("agent")
    closes = 0
    for alert in load_alerts(agent) + load_twins(agent):
        for framing in FRAMINGS:
            decided = decide(build_payload(frame(alert, framing))["items"])
            if decided is not None and decided[0] == "CLOSE":
                closes += 1
                assert decided[1].strip() and decided[2], alert["id"]
    assert closes > 100


def test_no_close_of_the_evaluation_run_or_the_close_reference_agent_lacks_a_reason(evaluation):
    rows = lines_of(evaluation["run_dir"].joinpath("items.jsonl"))
    closes = [row for row in rows if row["result"]["recommendation"] == "CLOSE"]
    assert closes and all(row["result"]["reason"].strip() for row in closes)
    result, _ = always_close(BUNDLE, None, SETTINGS, "X/1")
    assert result["recommendation"] == "CLOSE" and result["reason"].strip()
