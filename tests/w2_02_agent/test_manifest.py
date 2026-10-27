"""W2-02: a run of the upgraded agent names its own prompt and rule-code hash in its manifest, and its rule-code hash
is one of the run-set inputs, so runs that differ only in rule code are different run sets (DEC-W2-02-LAYOUT). Every
other agent's run-set inputs are as before, so the committed baseline keeps its run-set ID. The model call is replaced
here by a fixed answer, so no model and no child process is used."""
import hashlib
import json

import pytest

import triage_agent
from harness import agents
from harness import manifest as records
from harness import run as harness_run
from triage_agent import recommend as agent

from conftest import REPO

STUB = {"provider": "stub", "model": "stub-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30}
FIXTURES = REPO.joinpath("tests", "t06_harness", "fixtures")
BASELINE_SET = "f2e614d2d530dc65c1d9f4dbec452d93296f5f52420b0f7829ff4404e7a99305"


@pytest.fixture
def run_agent(practice_world, tmp_path, monkeypatch):
    def ask_model(items, model, settings, sink=None, retries=2, correlation_id=None):  # as the baseline call hands over
        result, records_ = agents.always_escalate(items, model, settings, correlation_id)
        sink.extend(records_)
        return result
    monkeypatch.setattr(agent, "ask_model", ask_model)
    tmp_path.joinpath("model.json").write_text(json.dumps(STUB), encoding="utf-8")

    def run(name, out="out"):
        config = {"agent": name, "world": str(practice_world), "model_config": "model.json", "workers": 2,
                  "pacer_per_minute": None, "infra_invalid_threshold": "0.05",
                  "price_table": str(FIXTURES.joinpath("prices.json")),
                  "modelled_time": str(FIXTURES.joinpath("modelled_time.json"))}
        tmp_path.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
        manifest = harness_run.run(tmp_path.joinpath("run.json"), tmp_path.joinpath(out))
        assert manifest["state"] == "completed"
        return manifest
    return run


def test_the_manifest_names_the_agents_own_prompt_and_rule_code_hash(run_agent):
    manifest = run_agent("triage")
    rules = hashlib.sha256(REPO.joinpath("triage_agent", "rules.py").read_bytes()).hexdigest()
    assert manifest["agent"] == "triage" and manifest["prompt"] == triage_agent.PROMPT
    assert manifest["prompt"]["rule_code_sha256"] == rules
    assert hashlib.sha256(manifest["prompt"]["text"].encode("utf-8")).hexdigest() == manifest["prompt"]["sha256"]
    assert manifest["run_set_inputs"]["prompt_hash"] == triage_agent.PROMPT["sha256"]
    assert manifest["run_set_inputs"]["rule_code_hash"] == rules


def test_two_runs_differing_only_in_rule_code_are_different_run_sets(run_agent, monkeypatch):
    first = run_agent("triage", "one")
    monkeypatch.setitem(harness_run.PROMPTS, "triage", {**triage_agent.PROMPT, "rule_code_sha256": "0" * 64})
    other = run_agent("triage", "two")
    differ = {key for key in first["run_set_inputs"] if first["run_set_inputs"][key] != other["run_set_inputs"][key]}
    assert differ == {"rule_code_hash"} and first["run_set"] != other["run_set"]
    assert other["prompt"]["rule_code_sha256"] == "0" * 64


def test_other_agents_add_no_rule_code_hash_and_the_baseline_keeps_its_run_set_id(run_agent):
    assert "rule_code_sha256" not in harness_run.PROMPTS["baseline"]
    assert "rule_code_hash" not in run_agent("always_escalate")["run_set_inputs"]
    for path in sorted(REPO.joinpath("baseline").glob("*/manifest.json")):
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert "rule_code_hash" not in committed["run_set_inputs"]
        assert committed["run_set"] == records.content_hash(committed["run_set_inputs"]) == BASELINE_SET
