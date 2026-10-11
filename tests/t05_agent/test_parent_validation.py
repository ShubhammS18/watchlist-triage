"""T05: the parent checks the whole result that comes back from the child (DEC-T05-PARENT-VALIDATION).

Each test puts a result in the place of what the child returns and asks `recommend` for the alert ALT-0002. A
result that breaks any rule must come out as ESCALATE with SYSTEM_FAILURE, kind child_crash. Found by the
independent review, docs/reviews/t05-review-round-1.md, finding 1.
"""
import copy

import pytest

import baseline_agent.recommend as parent
from test_agent import ITEMS, SETTINGS, check, is_failure, run

CHILD_LOG = {"kind": "ok", "error_name": None, "attempts": 1,
             "attempt_log": [{"error_name": None, "latency_s": 0.01}], "latency_s": 0.02, "model_id": "stub-1"}
CLOSE = {"recommendation": "CLOSE", "reason": "The dates of birth differ.", "cited_ids": ["EVD-00012", "EVD-00016"],
         "system_failure": False, "failure_kind": None, "citation_invalid": False, "log": CHILD_LOG}
ESCALATE = {**CLOSE, "recommendation": "ESCALATE"}
ESCALATE_UNKNOWN_ID = {**ESCALATE, "cited_ids": ["EVD-00012", "EVD-99999"], "citation_invalid": True}
FAILURE = {"recommendation": "ESCALATE", "reason": "System failure: timeout", "cited_ids": [], "system_failure": True,
           "failure_kind": "timeout", "citation_invalid": False,
           "log": {"kind": "timeout", "error_name": "ModelTimeout", "attempts": 3, "latency_s": 0.03, "model_id": None,
                   "attempt_log": [{"error_name": "ModelTimeout", "latency_s": 0.01}] * 3}}
KINDS = ("malformed_output", "missing_citations", "model_refusal", "timeout", "provider_error", "truncated_evidence",
         "unknown_schema_version", "invalid_citation", "model_error", "child_timeout", "child_crash", "internal_error")


def returned(monkeypatch, result):
    """What `recommend` makes of `result` coming back from the child."""
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: copy.deepcopy(result))
    return run()


def changed(base, log=None, **fields):
    result = {**copy.deepcopy(base), **fields}
    result["log"].update(log or {})
    return result


def without(base, key, in_log=False):
    result = copy.deepcopy(base)
    del (result["log"] if in_log else result)[key]
    return result


def test_a_close_with_no_reason_no_citations_and_a_failure_kind_does_not_leave_as_a_close(monkeypatch):
    # The case the review injected: recommend() returned it as CLOSE.
    result, log, calls = returned(monkeypatch, changed(CLOSE, reason="", cited_ids=[], failure_kind="timeout"))
    assert is_failure(result, "child_crash") and log[0]["error_name"] == "BadResult"


# The three cases the second review injected (docs/reviews/t05-review-round-2.md, finding 1): each came back CLOSE.
FORGED_LOGS = {
    "no attempts": {"attempts": 0, "attempt_log": []},
    "a top-level error name": {"error_name": "ModelTimeout"},
    "a final attempt with an error": {"attempt_log": [{"error_name": "ModelTimeout", "latency_s": 0.01}]},
}


@pytest.mark.parametrize("name", FORGED_LOGS)
def test_a_close_whose_log_contradicts_it_does_not_leave_as_a_close(monkeypatch, name):
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: changed(CLOSE, log=FORGED_LOGS[name]))
    result = parent.recommend(ITEMS, None, SETTINGS)
    assert (result["recommendation"], result["failure_kind"]) == ("ESCALATE", "child_crash"), result["recommendation"]


def test_a_close_whose_total_latency_is_shorter_than_one_of_its_attempts_does_not_leave_as_a_close(monkeypatch):
    # The case the third review injected: a total of 0 seconds with one attempt of 10 seconds came back CLOSE.
    forged = changed(CLOSE, log={"latency_s": 0, "attempt_log": [{"error_name": None, "latency_s": 10}]})
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: forged)
    result = parent.recommend(ITEMS, None, SETTINGS)
    assert (result["recommendation"], result["failure_kind"]) == ("ESCALATE", "child_crash"), result["recommendation"]


@pytest.mark.parametrize("good", [CLOSE, ESCALATE, ESCALATE_UNKNOWN_ID, FAILURE],
                         ids=["a close", "an escalate", "an escalate citing an unknown id", "a failure"])
def test_a_consistent_result_comes_through_as_the_child_gave_it(monkeypatch, good):
    result, log, calls = returned(monkeypatch, good)
    assert result == {**good, "log": {**good["log"], "correlation_id": None}}


def entries(*names):
    return [{"error_name": name, "latency_s": 0.01} for name in names]


def failed(kind, error_name, *attempt_errors, model_id=None, attempts=...):
    """A failure result as the child (or, for the last three kinds, the parent) writes it."""
    count = len(attempt_errors) if attempts is ... else attempts
    return changed(FAILURE, failure_kind=kind, reason=f"System failure: {kind}",
                   log={"kind": kind, "error_name": error_name, "model_id": model_id, "attempt_log": entries(*attempt_errors),
                        "attempts": count, "latency_s": 0.0 if count == 0 else 0.5})


TIMEOUTS = ("ModelTimeout",) * 3
# One consistent example of every way each of the twelve kinds can arrive, with the default 2 retries.
CONSISTENT_FAILURES = {
    "malformed_output, from a reply": failed("malformed_output", None, None, model_id="stub-1"),
    "malformed_output, from an empty reply": failed("malformed_output", "BadReply", "BadReply"),
    "missing_citations": failed("missing_citations", None, None, model_id="stub-1"),
    "invalid_citation, after a retry": failed("invalid_citation", None, "ProviderError", None, model_id="stub-1"),
    "unknown_schema_version, from a reply": failed("unknown_schema_version", None, None, model_id="stub-1"),
    "unknown_schema_version, from the payload": failed("unknown_schema_version", None),
    "truncated_evidence": failed("truncated_evidence", None),
    "model_refusal": failed("model_refusal", "ModelRefusal", "ModelRefusal"),
    "model_refusal, after a retry": failed("model_refusal", "ModelRefusal", "ModelTimeout", "ModelRefusal"),
    "timeout": failed("timeout", "ModelTimeout", *TIMEOUTS),
    "provider_error": failed("provider_error", "ProviderError", "ModelTimeout", "ProviderError", "ProviderError"),
    "model_error": failed("model_error", "ModelError", "ModelError"),
    "child_timeout": failed("child_timeout", "ChildTimeout", attempts=None),
    "child_crash": failed("child_crash", "ChildError", attempts=None),
    "child_crash, bad result": failed("child_crash", "BadResult", attempts=None),
    "internal_error": failed("internal_error", "RuntimeError", attempts=None),
}
CONSISTENT_SUCCESSES = {
    "a close whose one attempt took the whole time": changed(CLOSE, log={"latency_s": 0.01}),
    "a close that took no measurable time": changed(CLOSE, log={"latency_s": 0.0, "attempt_log": [{"error_name": None, "latency_s": 0.0}]}),
    "a close after two retries": changed(CLOSE, log={"attempts": 3, "attempt_log": entries("ModelTimeout", "ProviderError", None)}),
    "an escalate after one retry": changed(ESCALATE, log={"attempts": 2, "attempt_log": entries("ProviderError", None)}),
}


@pytest.mark.parametrize("name", {**CONSISTENT_FAILURES, **CONSISTENT_SUCCESSES})
def test_every_consistent_form_of_every_kind_is_accepted(monkeypatch, name):
    good = {**CONSISTENT_FAILURES, **CONSISTENT_SUCCESSES}[name]
    result, log, calls = returned(monkeypatch, good)
    assert result == {**good, "log": {**good["log"], "correlation_id": None}}


def test_the_examples_cover_exactly_the_twelve_kinds_the_parent_knows():
    assert {good["failure_kind"] for good in CONSISTENT_FAILURES.values()} == set(parent.KINDS) and len(parent.KINDS) == 12


def test_a_failure_the_parent_builds_itself_passes_its_own_check():
    for kind, error_name in (("child_timeout", "ChildTimeout"), ("child_crash", "ChildError"),
                             ("child_crash", "BadResult"), ("internal_error", "ValueError")):
        assert parent._valid(parent.failure(kind, error_name, latency_s=0.5), set(), 3)


def test_more_retries_allow_more_attempts(monkeypatch):
    five = changed(CLOSE, log={"attempts": 5, "attempt_log": entries(*["ModelTimeout"] * 4, None)})
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: copy.deepcopy(five))
    assert is_failure(run()[0], "child_crash")           # 2 retries: at most 3 attempts
    assert run(retries=4)[0]["recommendation"] == "CLOSE"  # 4 retries: 5 attempts are possible
    assert run(retries=5)[0]["recommendation"] == "CLOSE"  # and with more retries still


NOT_A_NUMBER = float("nan")
INCONSISTENT = {
    # ---- the key set and the types
    "a key missing": without(CLOSE, "citation_invalid"),
    "an extra key": changed(CLOSE, confidence=0.9),
    "a reason that is not text": changed(CLOSE, reason=["The dates of birth differ."]),
    "cited_ids that is not a list": changed(CLOSE, cited_ids="EVD-00012"),
    "a cited id that is not text": changed(CLOSE, cited_ids=["EVD-00012", 16]),
    "a failure flag that is not a boolean": changed(CLOSE, system_failure=0),
    "a citation flag that is not a boolean": changed(ESCALATE, citation_invalid=0),
    "an unknown recommendation": changed(CLOSE, recommendation="HOLD"),
    "a recommendation that is not text": changed(CLOSE, recommendation=["CLOSE"]),
    "an unknown failure kind": changed(FAILURE, failure_kind="made_up", reason="System failure: made_up", log={"kind": "made_up"}),
    "a failure kind that is not text": changed(FAILURE, failure_kind=["timeout"]),
    # ---- a failure must be an ESCALATE with its kind set
    "a failure that says CLOSE": changed(FAILURE, recommendation="CLOSE"),
    "a failure with no kind": changed(FAILURE, failure_kind=None),
    "a failure with cited ids": changed(FAILURE, cited_ids=["EVD-00012"]),
    "a failure with another reason": changed(FAILURE, reason="The dates of birth differ."),
    "a failure marked citation invalid": changed(FAILURE, citation_invalid=True),
    # ---- a result that is not a failure
    "a close with a failure kind": changed(CLOSE, failure_kind="timeout"),
    "an escalate with a failure kind": changed(ESCALATE, failure_kind="timeout"),
    "a close with an empty reason": changed(CLOSE, reason=""),
    "a close with a reason of spaces": changed(CLOSE, reason=" \n"),
    "a close with no cited ids": changed(CLOSE, cited_ids=[]),
    "a close citing an id outside the bundle": changed(CLOSE, cited_ids=["EVD-00012", "EVD-00001"]),
    "a close marked citation invalid": changed(CLOSE, citation_invalid=True),
    "a close citing an unknown id and marked so": changed(CLOSE, cited_ids=["EVD-99999"], citation_invalid=True),
    "an escalate with an empty reason": changed(ESCALATE, reason=""),
    "an escalate with no cited ids": changed(ESCALATE, cited_ids=[]),
    "an escalate citing an unknown id and not marked": changed(ESCALATE_UNKNOWN_ID, citation_invalid=False),
    "an escalate marked citation invalid with known ids": changed(ESCALATE, citation_invalid=True),
    # ---- the log record
    "a log that is not an object": {**CLOSE, "log": "ok"},
    "a log key missing": without(CLOSE, "model_id", in_log=True),
    "an extra log key": changed(CLOSE, log={"note": "x"}),
    "a correlation id from the child": changed(CLOSE, log={"correlation_id": "from-the-child"}),
    "a log kind that is not ok on a close": changed(CLOSE, log={"kind": "timeout"}),
    "a log kind that is not the failure kind": changed(FAILURE, log={"kind": "provider_error"}),
    "an error name that is not text": changed(FAILURE, log={"error_name": 7}),
    "a model id that is not text": changed(CLOSE, log={"model_id": 1}),
    "attempts as text": changed(CLOSE, log={"attempts": "1"}),
    "attempts as a boolean": changed(CLOSE, log={"attempts": True}),
    "attempts below zero": changed(FAILURE, log={"attempts": -1, "attempt_log": []}),
    "an attempt list that is not a list": changed(CLOSE, log={"attempt_log": None}),
    "an attempt list of the wrong length": changed(CLOSE, log={"attempts": 2}),
    "an attempt entry with an extra key": changed(CLOSE, log={"attempt_log": [{"error_name": None, "latency_s": 0.01, "text": "x"}]}),
    "an attempt entry that is not an object": changed(CLOSE, log={"attempt_log": ["ok"]}),
    "an attempt latency that is text": changed(CLOSE, log={"attempt_log": [{"error_name": None, "latency_s": "fast"}]}),
    "an attempt error name that is not text": changed(CLOSE, log={"attempt_log": [{"error_name": 1, "latency_s": 0.01}]}),
    "a latency that is text": changed(CLOSE, log={"latency_s": "0.02"}),
    "a latency below zero": changed(CLOSE, log={"latency_s": -1}),
    "a latency that is not a number": changed(CLOSE, log={"latency_s": NOT_A_NUMBER}),
    "a latency that is a boolean": changed(CLOSE, log={"latency_s": True}),
    "an attempt latency below zero": changed(CLOSE, log={"attempt_log": [{"error_name": None, "latency_s": -0.01}]}),
    "an attempt latency that is not finite": changed(CLOSE, log={"attempt_log": [{"error_name": None, "latency_s": float("inf")}]}),
    # ---- how the log must agree with a success (DEC-T05-LOG-INVARIANTS)
    "a close with no attempts": changed(CLOSE, log={"attempts": 0, "attempt_log": []}),
    "an escalate with no attempts": changed(ESCALATE, log={"attempts": 0, "attempt_log": []}),
    "a close with unknown attempts": changed(CLOSE, log={"attempts": None, "attempt_log": []}),
    "a close with a top-level error name": changed(CLOSE, log={"error_name": "ModelTimeout"}),
    "a close whose final attempt has an error": changed(CLOSE, log={"attempt_log": entries("ModelTimeout")}),
    "a close whose error name and final attempt agree": changed(CLOSE, log={"error_name": "ModelTimeout", "attempts": 3, "attempt_log": entries(*TIMEOUTS)}),
    "a close with no model id": changed(CLOSE, log={"model_id": None}),
    "a close after an earlier attempt that is not retried": changed(CLOSE, log={"attempts": 2, "attempt_log": entries("BadReply", None)}),
    "a close after an earlier attempt with no error": changed(CLOSE, log={"attempts": 2, "attempt_log": entries(None, None)}),
    "a close after an earlier refusal": changed(CLOSE, log={"attempts": 2, "attempt_log": entries("ModelRefusal", None)}),
    "a close with more attempts than allowed": changed(CLOSE, log={"attempts": 4, "attempt_log": entries(*TIMEOUTS, None)}),
    "a close whose total time is shorter than its attempt": changed(CLOSE, log={"latency_s": 0, "attempt_log": [{"error_name": None, "latency_s": 10}]}),
    "a close whose total time is shorter than an earlier attempt": changed(CLOSE, log={"attempts": 2, "latency_s": 0.05, "attempt_log": [{"error_name": "ModelTimeout", "latency_s": 0.06}, {"error_name": None, "latency_s": 0.01}]}),
    # ---- how the log must agree with a failure
    "a timeout whose total time is shorter than one attempt": changed(FAILURE, log={"attempt_log": [{"error_name": "ModelTimeout", "latency_s": 0.01}] * 2 + [{"error_name": "ModelTimeout", "latency_s": 0.031}]}),
    "truncated evidence with a total time": changed(failed("truncated_evidence", None), log={"latency_s": 0.01}),
    "an unknown payload schema version with a total time": changed(failed("unknown_schema_version", None), log={"latency_s": 2}),
    "a timeout with a provider error name": failed("timeout", "ProviderError", "ModelTimeout", "ModelTimeout", "ProviderError"),
    "a timeout with no error name": failed("timeout", None, "ModelTimeout", "ModelTimeout", None, model_id="stub-1"),
    "a timeout whose final attempt differs from its error name": failed("timeout", "ModelTimeout", "ModelTimeout", "ModelTimeout", "ProviderError"),
    "a timeout that stopped before the last attempt": failed("timeout", "ModelTimeout", "ModelTimeout"),
    "a timeout with more attempts than allowed": failed("timeout", "ModelTimeout", *TIMEOUTS, "ModelTimeout"),
    "a timeout with a model id": failed("timeout", "ModelTimeout", *TIMEOUTS, model_id="stub-1"),
    "a timeout with no attempts": failed("timeout", None),
    "a refusal with a timeout error name": failed("model_refusal", "ModelTimeout", *TIMEOUTS),
    "a refusal after an earlier refusal": failed("model_refusal", "ModelRefusal", "ModelRefusal", "ModelRefusal"),
    "a model error with a name that has its own kind": failed("model_error", "ModelRefusal", "ModelRefusal"),
    "malformed output with a refusal error name": failed("malformed_output", "ModelRefusal", "ModelRefusal"),
    "missing citations with an error name": failed("missing_citations", "BadReply", "BadReply"),
    "missing citations with no model id": failed("missing_citations", None, None),
    "missing citations with no attempts": failed("missing_citations", None),
    "truncated evidence with a model call": failed("truncated_evidence", None, None, model_id="stub-1"),
    "truncated evidence with a model id": failed("truncated_evidence", None, model_id="stub-1"),
    "truncated evidence with an error name": failed("truncated_evidence", "ModelTimeout"),
    "truncated evidence with unknown attempts": failed("truncated_evidence", None, attempts=None),
    "a child timeout with attempts": failed("child_timeout", "ChildTimeout", *TIMEOUTS),
    "a child timeout with zero attempts": failed("child_timeout", "ChildTimeout", attempts=0),
    "a child timeout with another error name": failed("child_timeout", "ChildError", attempts=None),
    "a child crash with an unknown error name": failed("child_crash", "ModelTimeout", attempts=None),
    "an internal error with no error name": failed("internal_error", None, attempts=None),
    "an internal error with a model id": failed("internal_error", "RuntimeError", attempts=None, model_id="stub-1"),
}


@pytest.mark.parametrize("name", INCONSISTENT)
def test_an_inconsistent_result_from_the_child_ends_as_child_crash(monkeypatch, name):
    result, log, calls = returned(monkeypatch, INCONSISTENT[name])  # run() also checks the shape of what comes out
    assert is_failure(result, "child_crash"), result
    assert (log[0]["error_name"], log[0]["attempts"], log[0]["attempt_log"]) == ("BadResult", None, [])


def test_the_ids_are_checked_against_this_alert_and_no_other(monkeypatch):
    other = [dict(item, id=item["id"].replace("EVD-000", "EVD-777")) for item in ITEMS]
    monkeypatch.setattr(parent, "run_child", lambda *args, **kwargs: copy.deepcopy(CLOSE))
    result, log, calls = run(items=other)  # CLOSE cites EVD-00012 and EVD-00016, which this alert does not have
    assert is_failure(result, "child_crash")
    check(result)
