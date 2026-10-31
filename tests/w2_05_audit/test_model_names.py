"""Model names in the log (DEC-W2-05-MODEL-ID): a name that fits the safe pattern is logged as it is, and any other
name, one with a space included, as "sha256:" and the hash of its text, so the run never aborts over it and the raw
text never reaches the log."""
import hashlib
import json
import math

import fake_model

from audit_common import T06_FIXTURES, write_config
from harness import audit
from harness import run as harness_run
from model_interface import Result


def hashed(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def test_a_safe_name_is_kept_and_any_other_is_hashed():
    assert audit.model_name("claude-haiku-5-5") == "claude-haiku-5-5"
    assert audit.model_name(123) == "number:123" and audit.model_name(math.nan) == "number:nan"
    for odd in ("fake model 1", "", "x" * 201, "Rev Tadrenä Tresketîs", "\ud800"):
        assert audit.model_name(odd) == hashed(odd)
    assert audit.MODEL(hashed("fake model 1"))


class Spaced(fake_model.Fake):
    """The fake model, reporting a model name with a space in it."""

    def __call__(self, request):
        result = super().__call__(request)
        return Result(result.text, "fake model 2", result.input_tokens, result.output_tokens, result.latency_s)


def run_with(tmp_path, monkeypatch, **model):
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "spaced", Spaced)
    monkeypatch.setattr(harness_run, "NOT_REAL", harness_run.NOT_REAL | {"spaced"})
    config = {**json.loads(T06_FIXTURES.joinpath("model_fake.json").read_text(encoding="utf-8")), **model}
    tmp_path.joinpath("model.json").write_text(json.dumps(config), encoding="utf-8")
    manifest = harness_run.run(write_config(tmp_path, model_config=str(tmp_path.joinpath("model.json"))),
                               tmp_path.joinpath("out"))
    folder = tmp_path.joinpath("out", manifest["run_id"])
    data = folder.joinpath(audit.LOG).read_bytes()
    assert manifest["state"] == "completed", manifest["aborted"]
    assert audit.verify(data, json.loads(folder.joinpath(audit.CHECKPOINT).read_text(encoding="utf-8"))) is None
    return [json.loads(line) for line in data.split(b"\n") if line], data


def test_a_requested_name_with_a_space_is_logged_as_its_hash(tmp_path, monkeypatch):
    records, data = run_with(tmp_path, monkeypatch, model="fake model 1")
    assert records[0]["requested_model"] == hashed("fake model 1") and b"fake model 1" not in data
    assert {name for r in records[1:-1] for name in r["model_ids"]} == {"fake-1"}   # the fake's own name, kept


def test_a_reported_name_with_a_space_is_logged_as_its_hash(tmp_path, monkeypatch):
    records, data = run_with(tmp_path, monkeypatch, provider="spaced")
    assert records[0]["requested_model"] == "fake-1"
    assert {name for r in records[1:-1] for name in r["model_ids"]} == {hashed("fake model 2")}
    assert b"fake model 2" not in data and len(records) == 1847
