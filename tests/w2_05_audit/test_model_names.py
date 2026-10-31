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


def test_a_real_name_that_looks_like_a_hash_is_hashed_too():
    """Review round 2: the literal name "sha256:<hash of x>" and the odd name x must not log the same."""
    odd = "fake model 2"
    literal = hashed(odd)
    assert audit.MODEL(literal)                                   # it fits the safe pattern, so it was kept before
    assert audit.model_name(literal) == hashed(literal) != audit.model_name(odd) == literal


class NotText(fake_model.Fake):
    """The fake model, reporting a model name that is not valid text: a lone surrogate cannot be encoded as UTF-8."""

    def __call__(self, request):
        result = super().__call__(request)
        return Result(result.text, "fake-\ud800", result.input_tokens, result.output_tokens, result.latency_s)


def test_a_reported_name_that_is_not_text_is_a_provider_fault_and_the_run_completes(tmp_path, monkeypatch):
    """Review round 2: before, the log hashed such a name and the run then crashed writing items.jsonl."""
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "not_text", NotText)
    monkeypatch.setattr(harness_run, "NOT_REAL", harness_run.NOT_REAL | {"not_text"})
    records, _ = run_with(tmp_path, monkeypatch, provider="not_text")
    folder = tmp_path.joinpath("out", records[0]["run_id"])
    manifest = json.loads(folder.joinpath("manifest.json").read_text(encoding="utf-8"))
    lines = [json.loads(line) for line in folder.joinpath("items.jsonl").read_text(encoding="utf-8").split("\n") if line]
    attempts = [one for line in lines for one in line["attempts"]]
    assert manifest["state"] == "completed" and manifest["model"]["reported"] == {} and len(lines) == 1845
    assert all(one["model_id"] is None for one in attempts)       # no such name reaches items.jsonl or the manifest
    assert "ProviderError" in {one["error"] for one in attempts}  # every answered call became a provider fault
    assert all(line["result"]["recommendation"] == "ESCALATE" and line["result"]["system_failure"] for line in lines)
    assert all(r["model_ids"] == [] for r in records[1:-1])
