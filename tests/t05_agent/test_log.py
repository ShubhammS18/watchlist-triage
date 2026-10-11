"""T05: what the log record of a result holds (DEC-T05-LOG-FIXES): one entry per model call, and the caller's
correlation id, which is added in the parent and goes nowhere else."""
import json

import pytest

import baseline_agent.recommend as parent
from baseline_agent.payload import build_payload
from baseline_agent.prompt import build_messages
from baseline_agent.recommend import recommend
from model_interface.stub import Stub
from test_agent import ITEMS, PROVIDER_ERROR, SETTINGS, TIMEOUT, check, is_failure, reply, run

CORRELATION_ID = "corr-7f3a91-run-2-framing-3"


def names(log):
    return [entry["error_name"] for entry in log["attempt_log"]]


# ---- one entry per model call

def test_two_timeouts_and_then_a_valid_reply_leave_three_entries():
    result, log, calls = run(TIMEOUT, TIMEOUT, reply())
    assert result["recommendation"] == "CLOSE" and calls == 3 == log[0]["attempts"]
    assert names(log[0]) == ["ModelTimeout", "ModelTimeout", None]
    for entry in log[0]["attempt_log"]:
        assert set(entry) == {"error_name", "latency_s"} and isinstance(entry["latency_s"], float)
        assert 0 <= entry["latency_s"] <= log[0]["latency_s"]
    assert sum(entry["latency_s"] for entry in log[0]["attempt_log"]) <= log[0]["latency_s"]


@pytest.mark.parametrize("steps, expected", [
    ([TIMEOUT] * 5, ["ModelTimeout"] * 3),
    ([PROVIDER_ERROR] * 5, ["ProviderError"] * 3),
    ([TIMEOUT, PROVIDER_ERROR, TIMEOUT], ["ModelTimeout", "ProviderError", "ModelTimeout"]),
], ids=["timeouts", "provider errors", "mixed"])
def test_three_failures_leave_three_entries(steps, expected):
    result, log, calls = run(*steps)
    assert result["system_failure"] and calls == 3 == log[0]["attempts"]
    assert names(log[0]) == expected and log[0]["error_name"] == expected[-1]


def test_one_call_leaves_one_entry_and_bad_output_has_no_error_name():
    assert names(run(reply())[1][0]) == [None]
    result, log, calls = run("not JSON")
    assert is_failure(result, "malformed_output") and names(log[0]) == [None]
    assert names(run(PROVIDER_ERROR, "not JSON")[1][0]) == ["ProviderError", None]


def test_a_failure_with_no_model_call_has_no_entries(monkeypatch):
    result, log, calls = run(items=[])
    assert log[0]["attempt_log"] == [] and log[0]["attempts"] is None and calls == 0
    monkeypatch.setattr(parent, "MODULE", "baseline_agent.no_such_module")
    assert run()[1][0]["attempt_log"] == []


# ---- the correlation id

def test_the_correlation_id_is_in_the_log_and_never_in_the_job_the_payload_or_the_prompt(monkeypatch):
    jobs, requests, real, stub = [], [], parent.run_child, Stub(default=reply())

    def spy(module, job, model, limit_s):
        jobs.append(json.dumps(job))
        return real(module, job, model, limit_s=limit_s)

    def model(request):
        requests.append(request)  # the parent makes the real call, so this is exactly what the model is sent
        return stub(request)

    monkeypatch.setattr(parent, "run_child", spy)
    sink = []
    result = recommend(ITEMS, model, SETTINGS, sink=sink, correlation_id=CORRELATION_ID)
    check(result)
    assert result["log"]["correlation_id"] == CORRELATION_ID and sink == [result["log"]]
    assert json.dumps(result).count(CORRELATION_ID) == 1

    assert len(jobs) == 1 and len(requests) == 1
    job = json.loads(jobs[0])
    assert set(job) == {"payload", "settings", "retries"} and job["payload"] == build_payload(ITEMS)
    assert CORRELATION_ID not in jobs[0] and "correlation" not in jobs[0]
    sent = json.dumps([[message.role, message.content] for message in requests[0].messages]) + repr(requests[0])
    assert CORRELATION_ID not in sent and "correlation" not in sent
    assert [{"role": m.role, "content": m.content} for m in requests[0].messages] == build_messages(job["payload"])


def test_the_correlation_id_is_none_unless_given_and_is_kept_as_given_on_a_failure(monkeypatch):
    assert run()[0]["log"]["correlation_id"] is None
    assert run(TIMEOUT, default=TIMEOUT, correlation_id=CORRELATION_ID)[0]["log"]["correlation_id"] == CORRELATION_ID
    opaque = {"run": 2, "alert": "ALT-0002"}
    assert run("not JSON", correlation_id=opaque)[0]["log"]["correlation_id"] is opaque
    monkeypatch.setattr(parent, "MODULE", "baseline_agent.no_such_module")
    result = run(correlation_id=CORRELATION_ID)[0]
    assert is_failure(result, "child_crash") and result["log"]["correlation_id"] == CORRELATION_ID


# ---- a sink that fails

def test_an_exception_from_the_sink_is_passed_on_and_no_result_comes_back():
    class Broken:
        def append(self, record):
            raise RuntimeError("the log could not be written")

    for stub in (Stub(default=reply()), Stub(default=TIMEOUT)):  # a CLOSE and a failure: neither is returned
        with pytest.raises(RuntimeError, match="the log could not be written"):
            recommend(ITEMS, stub, SETTINGS, sink=Broken())


def test_a_sink_that_changes_its_record_leaves_the_returned_close_intact():
    class Meddling:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(dict(record))
            record["attempt_log"].clear()
            record.clear()
            record["kind"] = "timeout"

    sink = Meddling()
    result = recommend(ITEMS, Stub(default=reply()), SETTINGS, sink=sink, correlation_id=CORRELATION_ID)
    check(result)  # the full seven-key log is still there
    assert result["recommendation"] == "CLOSE" and result["log"]["kind"] == "ok"
    assert result["log"]["attempts"] == 1 == len(result["log"]["attempt_log"])
    assert sink.records[0]["correlation_id"] == CORRELATION_ID and sink.records[0]["attempts"] == 1


def test_the_sink_gets_a_copy_that_later_changes_to_the_result_do_not_reach():
    sink = []
    result = recommend(ITEMS, Stub(default=reply()), SETTINGS, sink=sink)
    assert sink == [result["log"]] and sink[0] is not result["log"]
    assert sink[0]["attempt_log"] is not result["log"]["attempt_log"]
    assert sink[0]["attempt_log"][0] is not result["log"]["attempt_log"][0]
    result["log"]["attempt_log"][0]["error_name"] = "changed later"
    assert sink[0]["attempt_log"][0]["error_name"] is None
