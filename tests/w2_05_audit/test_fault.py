"""An audit-write failure is a harness fault (DEC-W2-05-AUDIT-FAULT): the run takes no new items, waits for the calls in
flight so its cost stays complete, and ends aborted with AuditWriteError; it never counts toward the three valid runs.
A counting model shows that every call made is in the run's cost."""
import json
import threading
import time

import fake_model
import pytest

from audit_common import T06_FIXTURES, WORLD, write_config
from harness import audit
from harness import run as harness_run
from harness import score

CALLS, LOCK = [], threading.Lock()


class Counted(fake_model.Fake):
    """The fake model, noting every call it receives, after an optional pause."""

    def __init__(self, delay=0):
        super().__init__()
        self._delay = delay

    def __call__(self, request):
        with LOCK:
            CALLS.append(1)
        time.sleep(self._delay)
        return super().__call__(request)


@pytest.fixture(autouse=True)
def counted(monkeypatch):
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "counted", Counted)
    monkeypatch.setattr(harness_run, "NOT_REAL", harness_run.NOT_REAL | {"counted"})
    CALLS.clear()


def config(folder, delay=0, **changes):
    model = {**json.loads(T06_FIXTURES.joinpath("model_fake.json").read_text(encoding="utf-8")), "provider": "counted",
             "options": {"delay": delay}}
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("model.json").write_text(json.dumps(model), encoding="utf-8")
    return write_config(folder, model_config=str(folder.joinpath("model.json")), **changes)


def failing_at(monkeypatch, at):
    """Make the `at`-th line written to any audit log (counted from 0) fail, and every later one."""
    real, count = audit.Log._emit, {"n": 0}

    def emit(self, data):
        count["n"] += 1
        if count["n"] > at:
            raise OSError("no space left on the test device")
        real(self, data)

    monkeypatch.setattr(audit.Log, "_emit", emit)


def kept_log(run_dir):
    """The records of an aborted run's log, after checking it against the checkpoint it wrote."""
    data = run_dir.joinpath(audit.LOG).read_bytes()
    trusted = json.loads(run_dir.joinpath(audit.CHECKPOINT).read_text(encoding="utf-8"))
    assert audit.verify(data, trusted) is None
    return [json.loads(line) for line in data.split(b"\n") if line]


def assert_aborted_by_the_log(manifest, out):
    assert manifest["state"] == "aborted" and manifest["outputs"] is None
    assert manifest["aborted"]["error_type"] == "AuditWriteError"
    assert manifest["calls"]["attempts"] == len(CALLS) == manifest["cost"]["attempts"]   # every call is in the cost
    entry = [run for run in json.loads(out.joinpath("index.json").read_text())["runs"] if run["run_id"] == manifest["run_id"]]
    assert entry[0]["state"] == "aborted" and entry[0]["cause"].startswith("AuditWriteError: ")
    assert not out.joinpath(manifest["run_id"], "items.jsonl").exists()


def test_a_failed_write_mid_run_aborts_it_and_keeps_every_call_in_the_cost(tmp_path, monkeypatch):
    failing_at(monkeypatch, 101)                     # run_started and 100 recommendations are written
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(config(tmp_path), out)
    assert_aborted_by_the_log(manifest, out)
    records = kept_log(out.joinpath(manifest["run_id"]))
    assert [r["event"] for r in records] == ["run_started"] + ["recommendation"] * 100   # no run_ended: the log failed
    assert manifest["items"]["total"] == 100
    assert manifest["aborted"]["item_id"] not in {r["item_id"] for r in records[1:]}   # the item it could not log


def test_in_a_parallel_run_the_calls_in_flight_are_waited_for(tmp_path, monkeypatch):
    failing_at(monkeypatch, 21)
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(config(tmp_path, delay=0.05, workers=4), out)
    made = len(CALLS)
    time.sleep(0.3)
    assert len(CALLS) == made                        # no call was still running when the run returned
    assert_aborted_by_the_log(manifest, out)
    assert 20 <= manifest["items"]["total"] < 100
    assert manifest["calls"]["attempts"] > manifest["items"]["total"]   # the items it could not log are counted too
    assert len(kept_log(out.joinpath(manifest["run_id"]))) == 21


def test_a_failed_first_write_aborts_the_run_before_any_call(tmp_path, monkeypatch):
    failing_at(monkeypatch, 0)
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(config(tmp_path), out)
    assert_aborted_by_the_log(manifest, out)
    assert manifest["aborted"]["item_id"] is None and len(CALLS) == 0
    assert kept_log(out.joinpath(manifest["run_id"])) == []


def test_a_failed_last_write_aborts_a_run_whose_items_were_all_made(tmp_path, monkeypatch):
    failing_at(monkeypatch, 1846)                    # every record but run_ended
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(config(tmp_path), out)
    assert_aborted_by_the_log(manifest, out)
    assert manifest["items"]["total"] == 1845 and manifest["aborted"]["item_id"] is None
    assert len(kept_log(out.joinpath(manifest["run_id"]))) == 1846


def test_a_failure_to_sync_the_log_aborts_the_run_and_leaves_no_checkpoint(tmp_path, monkeypatch):
    def refuse(descriptor):
        raise OSError("the test device cannot sync")

    monkeypatch.setattr(audit.os, "fsync", refuse)
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(config(tmp_path), out)
    assert_aborted_by_the_log(manifest, out)
    assert not out.joinpath(manifest["run_id"], audit.CHECKPOINT).exists()


def test_a_run_aborted_by_the_log_never_counts_toward_the_valid_runs(tmp_path, monkeypatch):
    """Both runs as if at one clean commit, with no infrastructure-invalid mark, so the good one is valid."""
    monkeypatch.setattr(harness_run.records, "git_state", lambda repo, out: ("c" * 40, False))
    out = tmp_path.joinpath("out")
    good = harness_run.run(config(tmp_path.joinpath("a"), infra_invalid_threshold="1"), out)
    failing_at(monkeypatch, 101)
    bad = harness_run.run(config(tmp_path.joinpath("b"), infra_invalid_threshold="1"), out)
    assert good["run_set"] == bad["run_set"] and (good["state"], bad["state"]) == ("completed", "aborted")
    report = score.score_all(out, WORLD)["sets"][good["run_set"]]
    assert report["valid_runs"] == 1
    assert [run["run_id"] for run in report["aborted"]["runs"]] == [bad["run_id"]]
    assert {run["run_id"]: run["valid"] for run in report["runs"]} == {good["run_id"]: True, bad["run_id"]: False}


def test_a_record_that_does_not_fit_its_types_is_refused_and_the_log_stops(tmp_path):
    log = audit.Log(tmp_path, "20261031T000000000000Z-abcdef01")
    with pytest.raises(audit.AuditWriteError, match="refused: these fields do not have their type"):
        log.write("run_ended", state="completed", items=1.5, items_sha256=None, aborted_item_id=None, error_type=None)
    with pytest.raises(audit.AuditWriteError, match="failed earlier"):
        log.write("run_ended", state="completed", items=1, items_sha256=None, aborted_item_id=None, error_type=None)
    log.close()
    assert tmp_path.joinpath(audit.LOG).read_bytes() == b""


def test_a_string_that_cannot_be_encoded_is_an_audit_write_error(tmp_path):
    """Review round 1: building, hashing and encoding a record are one guarded step, the body made inside it too."""
    lone = "\ud800"  # a lone surrogate: valid in a Python string, not encodable as UTF-8
    for folder in ("a", "b"):
        tmp_path.joinpath(folder).mkdir()
    log = audit.Log(tmp_path.joinpath("a"), "20261031T000000000000Z-abcdef01")
    with pytest.raises(audit.AuditWriteError, match="UnicodeEncodeError"):   # a field given directly
        log.write("run_ended", state="aborted", items=0, items_sha256=None, aborted_item_id=None, error_type=lone)
    log = audit.Log(tmp_path.joinpath("b"), "20261031T000000000000Z-abcdef01")
    line = {"item_id": "ALT-0001/1", "alert_id": "ALT-0001", "framing": 1, "twin": False, "sent_ids": ["EVD-00001"],
            "attempts": [], "result": {"recommendation": "ESCALATE", "reason": "r", "cited_ids": [lone],
                                       "system_failure": False, "failure_kind": None, "citation_invalid": True}}
    with pytest.raises(audit.AuditWriteError, match="UnicodeEncodeError"):   # a cited ID, hashed while the body is made
        log.write("recommendation", make=lambda: audit.recommendation(line, "a" * 64))
    for folder in ("a", "b"):
        assert tmp_path.joinpath(folder, audit.LOG).read_bytes() == b""
