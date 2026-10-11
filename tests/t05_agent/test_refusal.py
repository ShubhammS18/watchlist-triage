"""T05: a model that refuses (DEC-T05-FAULTS, AC-13 "model refusal").

A refusal here is the named error ModelRefusal, which the stub raises on a "refusal" step. A refusal written as
plain words in a reply is not recognised as one: it is bad output and ends as malformed_output.
"""
import pytest

from model_interface import ERRORS, ModelError, ModelRefusal, Request
from model_interface.runner import run_child
from model_interface.stub import Stub
from test_agent import SETTINGS, TIMEOUT, is_failure, run

REFUSAL = {"fail": "refusal"}
REQUEST = {"messages": [{"role": "user", "content": "hello"}],
           "settings": {"model": "stub-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30}}


def test_the_stub_refusal_step_raises_the_named_error():
    with pytest.raises(ModelRefusal) as caught:
        Stub(replies=[REFUSAL])(Request(REQUEST["messages"], SETTINGS))
    assert isinstance(caught.value, ModelError) and ERRORS["ModelRefusal"] is ModelRefusal


def test_a_refusal_crosses_the_pipe_under_its_own_name():
    assert run_child("model_interface.probe_child", {"request": REQUEST}, Stub(default=REFUSAL)) == {
        "model_error": "ModelRefusal"}


def test_a_refusal_is_escalated_as_a_system_failure_after_one_attempt_with_a_log_entry():
    result, log, calls = run(REFUSAL)  # the stub would answer a valid CLOSE if it were asked a second time
    assert is_failure(result, "model_refusal")
    assert (result["recommendation"], result["reason"], result["cited_ids"]) == (
        "ESCALATE", "System failure: model_refusal", [])
    assert calls == 1 and len(log) == 1
    assert (log[0]["kind"], log[0]["error_name"], log[0]["attempts"]) == ("model_refusal", "ModelRefusal", 1)
    assert [entry["error_name"] for entry in log[0]["attempt_log"]] == ["ModelRefusal"]


def test_a_model_that_always_refuses_is_asked_once():
    result, log, calls = run(default=REFUSAL)
    assert is_failure(result, "model_refusal") and calls == 1 and log[0]["attempts"] == 1


def test_a_refusal_after_a_timeout_ends_the_run_there():
    result, log, calls = run(TIMEOUT, REFUSAL)
    assert is_failure(result, "model_refusal") and calls == 2
    assert [entry["error_name"] for entry in log[0]["attempt_log"]] == ["ModelTimeout", "ModelRefusal"]


def test_a_refusal_in_plain_words_is_bad_output_not_a_refusal():
    result, log, calls = run("I'm sorry, but I can't help with that request.")
    assert is_failure(result, "malformed_output") and calls == 1
