"""T05: the baseline agent end to end with the stub model (FR-6, FR-7, FR-8 model faults, AC-2, AC-13, AC-21).

Unless a test says otherwise, every call goes through `recommend`, so the agent really runs in the guarded child
process. The stub plays back scripted replies; nothing here shows what a real model would answer.
"""
import json
import time

import pytest

import baseline_agent.recommend as parent
from baseline_agent.payload import build_payload
from baseline_agent.recommend import recommend
from model_interface import Settings
from model_interface.stub import MODEL_ID, Stub
from test_payload_prompt import BY_ID, HIDDEN, LABEL_VALUES, keys_in

ITEMS = BY_ID["ALT-0002"]["evidence"]  # eight items, EVD-00011 to EVD-00018
IDS = {item["id"] for item in ITEMS}
SETTINGS = Settings(model="stub-1", temperature=0, max_tokens=512, timeout_s=30)
TIMEOUT, PROVIDER_ERROR, EMPTY = {"fail": "timeout"}, {"fail": "provider_error"}, {"fail": "empty"}


def reply(recommendation="CLOSE", cited_ids=("EVD-00012", "EVD-00016"), reason="The dates of birth differ.", **changes):
    fields = {"schema_version": "1", "recommendation": recommendation, "reason": reason, "cited_ids": list(cited_ids) if isinstance(cited_ids, tuple) else cited_ids}
    fields.update(changes)
    return json.dumps({key: value for key, value in fields.items() if value is not ...})


class Counting:
    """A model that counts its calls and passes them on."""

    def __init__(self, model):
        self.model, self.calls = model, 0

    def __call__(self, request):
        self.calls += 1
        return self.model(request)


def run(*replies, default=None, items=ITEMS, **options):
    """(result, log records, number of model calls) for one alert and a scripted stub."""
    model, sink = Counting(Stub(default=reply() if default is None else default, replies=replies)), []
    result = recommend(items, model, SETTINGS, sink=sink, **options)
    check(result)
    assert sink == [result["log"]]
    return result, sink, model.calls


def check(result):
    """What must hold for every result, whatever happened."""
    assert set(result) == parent.RESULT_KEYS and json.loads(json.dumps(result)) == result
    log = result["log"]
    assert set(log) == {"kind", "error_name", "attempts", "attempt_log", "latency_s", "model_id", "correlation_id"}
    assert isinstance(log["attempt_log"], list) and len(log["attempt_log"]) == (log["attempts"] or 0)
    assert all(set(entry) == {"error_name", "latency_s"} for entry in log["attempt_log"])
    assert result["recommendation"] in ("CLOSE", "ESCALATE")
    assert not (keys_in(result) & HIDDEN) and not [v for v in LABEL_VALUES if v in json.dumps(result)]
    if result["system_failure"]:
        kind = result["failure_kind"]
        assert kind and result["log"]["kind"] == kind
        assert (result["recommendation"], result["reason"], result["cited_ids"]) == ("ESCALATE", f"System failure: {kind}", [])
    else:
        assert result["failure_kind"] is None and result["log"]["kind"] == "ok"
        assert result["reason"].strip() and result["cited_ids"]
    if result["recommendation"] == "CLOSE":
        assert not result["system_failure"] and not result["citation_invalid"] and set(result["cited_ids"]) <= IDS


def is_failure(result, kind):
    return result["recommendation"] == "ESCALATE" and result["system_failure"] and result["failure_kind"] == kind


# ---- a reply that can be used

def test_a_valid_close_comes_back_with_its_reason_and_citations():
    result, log, calls = run(reply("CLOSE"))
    latency, [attempt] = result["log"].pop("latency_s"), result["log"].pop("attempt_log")
    assert result == {"recommendation": "CLOSE", "reason": "The dates of birth differ.",
                      "cited_ids": ["EVD-00012", "EVD-00016"], "system_failure": False, "failure_kind": None,
                      "citation_invalid": False,
                      "log": {"kind": "ok", "error_name": None, "attempts": 1, "model_id": MODEL_ID,
                              "correlation_id": None}}
    assert isinstance(latency, float) and 0 <= attempt["latency_s"] <= latency < 5 and calls == 1
    assert attempt["error_name"] is None


def test_a_valid_escalate_comes_back_with_its_reason_and_citations():
    result, log, calls = run(reply("ESCALATE", ["EVD-00011"], "The evidence does not settle it."))
    assert (result["recommendation"], result["reason"], result["cited_ids"]) == (
        "ESCALATE", "The evidence does not settle it.", ["EVD-00011"])
    assert not result["system_failure"] and not result["citation_invalid"] and calls == 1


def test_there_is_no_module_level_log_list_and_a_result_carries_its_log_without_a_sink():
    import baseline_agent
    from baseline_agent import agent, payload, prompt, reply as reply_module
    for module in (baseline_agent, agent, parent, payload, prompt, reply_module):
        assert not hasattr(module, "LOG")
        lists = [name for name, value in vars(module).items() if isinstance(value, list) and not name.startswith("__")]
        assert not lists, module.__name__
    result = recommend(ITEMS, Stub(default=reply()), SETTINGS)
    check(result)
    assert result["log"]["kind"] == "ok" and result["log"]["attempts"] == 1


# ---- a reply that cannot be used: ESCALATE with SYSTEM_FAILURE and a log entry, after exactly one call

BAD_OUTPUT = {
    "not JSON": ("I think this one can be closed.", "malformed_output"),
    "JSON with text around it": ("Here you go: " + reply(), "malformed_output"),
    "a JSON list": (json.dumps([json.loads(reply())]), "malformed_output"),
    "two JSON objects": (reply() + "\n" + reply(), "malformed_output"),
    "an extra key": (reply(confidence=0.9), "malformed_output"),
    "no reason key": (reply(reason=...), "malformed_output"),
    "no cited_ids key": (reply(cited_ids=...), "malformed_output"),
    "no schema_version key": (reply(schema_version=...), "malformed_output"),
    "an unknown recommendation": (reply("HOLD"), "malformed_output"),
    "a lower-case recommendation": (reply("close"), "malformed_output"),
    "a reason that is not text": (reply(reason=["a"]), "malformed_output"),
    "cited_ids that is not a list": (reply(cited_ids="EVD-00012"), "malformed_output"),
    "a cited id that is not text": (reply(cited_ids=[12]), "malformed_output"),
    "an empty reply": (EMPTY, "malformed_output"),
    "schema version 2": (reply(schema_version="2"), "unknown_schema_version"),
    "schema version as a number": (reply(schema_version=1), "unknown_schema_version"),
    "schema version 2 and nothing else": (json.dumps({"schema_version": "2"}), "unknown_schema_version"),
    "an empty reason": (reply(reason=""), "missing_citations"),
    "a reason of spaces": (reply(reason="  \n"), "missing_citations"),
    "no cited ids on a CLOSE": (reply("CLOSE", []), "missing_citations"),
    "no cited ids on an ESCALATE": (reply("ESCALATE", []), "missing_citations"),
    "a CLOSE citing an id outside the bundle": (reply("CLOSE", ["EVD-00012", "EVD-00001"]), "invalid_citation"),
    "a CLOSE citing only an id outside the bundle": (reply("CLOSE", ["EVD-99999"]), "invalid_citation"),
}


@pytest.mark.parametrize("name", BAD_OUTPUT)
def test_bad_output_is_escalated_as_a_system_failure_and_not_tried_again(name):
    text, kind = BAD_OUTPUT[name]
    result, log, calls = run(text)  # the stub would answer a valid CLOSE if it were asked a second time
    assert is_failure(result, kind), result
    assert calls == 1 and log[0]["attempts"] == 1 and log[0]["kind"] == kind
    assert log[0]["error_name"] == ("BadReply" if text is EMPTY else None)


def test_an_escalate_citing_an_unknown_id_stays_an_escalate_and_is_marked():
    result, log, calls = run(reply("ESCALATE", ["EVD-00012", "EVD-99999"]))
    assert (result["recommendation"], result["system_failure"], result["citation_invalid"]) == ("ESCALATE", False, True)
    assert result["cited_ids"] == ["EVD-00012", "EVD-99999"] and result["failure_kind"] is None


# ---- timeouts and provider errors are tried again, at most twice

def test_two_timeouts_and_then_a_valid_reply_take_three_attempts():
    result, log, calls = run(TIMEOUT, TIMEOUT, reply("CLOSE"))
    assert result["recommendation"] == "CLOSE" and not result["system_failure"]
    assert calls == 3 and log[0]["attempts"] == 3


def test_a_provider_error_and_then_a_valid_reply_take_two_attempts():
    result, log, calls = run(PROVIDER_ERROR, reply("ESCALATE"))
    assert result["recommendation"] == "ESCALATE" and not result["system_failure"]
    assert calls == 2 and log[0]["attempts"] == 2


@pytest.mark.parametrize("step, kind, error_name", [(TIMEOUT, "timeout", "ModelTimeout"),
                                                    (PROVIDER_ERROR, "provider_error", "ProviderError")])
def test_a_fault_that_does_not_go_away_fails_after_three_attempts(step, kind, error_name):
    result, log, calls = run(*[step] * 5)  # a sixth call would get a valid CLOSE
    assert is_failure(result, kind)
    assert calls == 3 and log[0] == {"kind": kind, "error_name": error_name, "attempts": 3,
                                     "attempt_log": log[0]["attempt_log"], "latency_s": log[0]["latency_s"],
                                     "model_id": None, "correlation_id": None}


def test_the_last_fault_names_the_failure():
    assert is_failure(run(TIMEOUT, PROVIDER_ERROR, TIMEOUT)[0], "timeout")
    assert is_failure(run(TIMEOUT, TIMEOUT, PROVIDER_ERROR)[0], "provider_error")


def test_bad_output_after_a_timeout_ends_the_run_there():
    result, log, calls = run(TIMEOUT, "not JSON")
    assert is_failure(result, "malformed_output") and calls == 2 and log[0]["attempts"] == 2


def test_the_number_of_retries_can_be_set_and_must_be_a_whole_number():
    result, log, calls = run(TIMEOUT, retries=0)
    assert is_failure(result, "timeout") and calls == 1
    for bad in (-1, 1.5, True, None):
        with pytest.raises(ValueError, match="retries"):
            recommend(ITEMS, Stub(), SETTINGS, retries=bad)


# ---- a payload that arrives damaged: no model call

def damaged(monkeypatch, change):
    def build(items):
        payload = build_payload(items)
        change(payload)
        return payload
    monkeypatch.setattr(parent, "build_payload", build)
    return run()


@pytest.mark.parametrize("change, kind", [
    (lambda payload: payload["items"].pop(), "truncated_evidence"),
    (lambda payload: payload.update(item_count=9), "truncated_evidence"),
    (lambda payload: payload.pop("item_count"), "truncated_evidence"),
    (lambda payload: payload.update(schema_version="2"), "unknown_schema_version"),
    (lambda payload: payload.pop("schema_version"), "unknown_schema_version"),
], ids=["an item lost", "a count too high", "no count", "schema version 2", "no schema version"])
def test_a_damaged_payload_is_a_system_failure_and_the_model_is_never_asked(monkeypatch, change, kind):
    result, log, calls = damaged(monkeypatch, change)
    assert is_failure(result, kind) and calls == 0 and log[0]["attempts"] == 0


# ---- the child process itself fails: the parent still answers ESCALATE

def test_the_child_gets_only_the_payload_the_settings_and_the_retries_and_a_limit_above_all_attempts(monkeypatch):
    seen = {}

    def fake(module, job, model, limit_s):
        seen.update(module=module, job=job, limit_s=limit_s)
        return parent.failure("truncated_evidence")
    monkeypatch.setattr(parent, "run_child", fake)
    recommend(ITEMS, Stub(), SETTINGS, sink=[])
    assert seen["module"] == "baseline_agent.agent" and seen["limit_s"] == (1 + 2) * 30 + 10 == 100
    assert seen["job"] == {"payload": build_payload(ITEMS), "retries": 2,
                           "settings": {"model": "stub-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30}}
    assert not keys_in(seen["job"]) & HIDDEN and not [v for v in LABEL_VALUES if v in json.dumps(seen["job"])]  # AC-21
    recommend(ITEMS, Stub(), Settings("stub-1", 0, 512, 7.5), sink=[], retries=0)
    assert seen["limit_s"] == 17.5


def test_a_model_that_never_answers_ends_as_child_timeout(monkeypatch):
    monkeypatch.setattr(parent, "MARGIN_S", 0.3)
    sink, begun = [], time.monotonic()
    result = recommend(ITEMS, lambda request: time.sleep(3), Settings("stub-1", 0, 512, 0.1), sink=sink, retries=0)
    assert time.monotonic() - begun < 2
    check(result)
    assert is_failure(result, "child_timeout") and sink == [result["log"]]
    assert (result["log"]["error_name"], result["log"]["attempts"]) == ("ChildTimeout", None)


def test_a_child_that_crashes_ends_as_child_crash(monkeypatch):
    monkeypatch.setattr(parent, "MODULE", "baseline_agent.no_such_module")
    result, log, calls = run()
    assert is_failure(result, "child_crash") and log[0]["error_name"] == "ChildError" and calls == 0


@pytest.mark.parametrize("returned", [None, "CLOSE", {"recommendation": "CLOSE"},
                                      {**parent.failure("timeout"), "recommendation": "CLOSE"},
                                      {**parent.failure("timeout"), "system_failure": "no"}],
                         ids=["nothing", "a word", "a bare CLOSE", "a failure that says CLOSE", "a flag that is not a boolean"])
def test_a_result_of_the_wrong_shape_from_the_child_ends_as_child_crash(monkeypatch, returned):
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: returned)
    result, log, calls = run()
    assert is_failure(result, "child_crash") and log[0]["error_name"] == "BadResult"


def test_a_fault_inside_the_model_object_or_an_alert_with_no_items_does_not_raise():
    def broken(request):
        raise RuntimeError("the adapter has a bug")
    sink = []
    result = recommend(ITEMS, broken, SETTINGS, sink=sink)
    check(result)
    assert is_failure(result, "internal_error") and sink[0]["error_name"] == "RuntimeError"
    result, log, calls = run(items=[])
    assert is_failure(result, "internal_error") and log[0]["error_name"] == "PayloadError" and calls == 0


# ---- across everything above

def test_no_fault_of_any_kind_gives_a_close():
    steps = [text for text, kind in BAD_OUTPUT.values()] + [TIMEOUT, PROVIDER_ERROR]
    results = [run(step, default=step)[0] for step in steps]  # run() checks every result
    assert len(results) == 25 and all(r["recommendation"] == "ESCALATE" and r["system_failure"] for r in results)
    assert {r["failure_kind"] for r in results} == {"malformed_output", "unknown_schema_version", "missing_citations",
                                                    "invalid_citation", "timeout", "provider_error"}
