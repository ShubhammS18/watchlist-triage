"""T07: the trial script and its hand-written alerts (DEC-T07-TRIAL), with the fake API on this machine."""
import json
import re

import pytest

from baseline_agent.payload import build_payload
from baseline_run import trial
from harness.manifest import REPO
from worldgen.loader import load_alerts

from fake_api import OK, answer, server  # noqa: F401  (server is a fixture)

ALERTS = json.loads(trial.ALERTS.read_text(encoding="utf-8"))


def reply(text, model="claude-haiku-5-5", output_tokens=40, **extra):
    return {**OK, "model": model, "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 600, "output_tokens": output_tokens}, **extra}


def verdict_of(body, recommendation="ESCALATE"):
    first = re.search(r'"id": "(TEV-\d+)"', body["messages"][-1]["content"]).group(1)
    return json.dumps({"schema_version": "1", "recommendation": recommendation, "reason": "r", "cited_ids": [first]})


@pytest.fixture
def model_config(tmp_path, server):
    path = tmp_path.joinpath("model.json")
    config = json.loads(trial.MODEL_CONFIG.read_text(encoding="utf-8"))
    config["options"]["base_url"] = server.url
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_every_trial_alert_is_one_call_and_every_verdict_passes(tmp_path, server, model_config, capsys):
    server.script = lambda h, body: answer(h, 200, reply(verdict_of(body)))
    results = trial.trial(tmp_path.joinpath("out"), model_config)
    assert len(results["rows"]) == len(ALERTS) == len(server.requests)
    assert all(row["valid_json"] and row["recommendation"] == "ESCALATE" and row["stop_reason_derived"] == "end_turn"
               and row["cost_usd"] == "0.00008" for row in results["rows"])  # 600 x 0.10 + 40 x 0.50 per million
    assert all(one["pass"] for one in results["verdicts"].values())
    assert json.loads(tmp_path.joinpath("out", "trial-results.json").read_text()) == results
    assert trial.show(results) == 0
    printed = capsys.readouterr().out
    for words in ("vs 10 s: PASS", "vs 256 and the 512 cap: PASS", "refusals 0: PASS",
                  "vs the price table key 'claude-haiku-5-5': PASS", "stop_reason(derived)"):
        assert words in printed


def test_a_refusal_an_answer_at_the_cap_and_another_model_id_fail_their_verdicts(tmp_path, server, model_config, capsys):
    alerts = tmp_path.joinpath("three.json")
    alerts.write_text(json.dumps(ALERTS[:3]), encoding="utf-8")

    def script(handler, body):
        content = body["messages"][-1]["content"]
        if "TEV-0101" in content:
            answer(handler, 200, {**OK, "content": [], "stop_reason": "refusal"})
        elif "TEV-0201" in content:
            answer(handler, 200, reply(verdict_of(body), output_tokens=512))
        else:
            answer(handler, 200, reply(verdict_of(body, "CLOSE"), model="claude-haiku-5-5-20261001"))
    server.script = script
    results = trial.trial(tmp_path.joinpath("out"), model_config, alerts)
    first, second, third = results["rows"]
    assert first["stop_reason_derived"] == "refusal" and first["failure_kind"] == "model_refusal"
    assert second["stop_reason_derived"] == "max_tokens" and third["recommendation"] == "CLOSE"
    v = results["verdicts"]
    assert (v["refusals"]["value"], v["largest_output_tokens"]["value"]) == (1, 512)
    assert v["model_ids"]["value"] == ["claude-haiku-5-5", "claude-haiku-5-5-20261001"]
    assert not any(one["pass"] for one in (v["refusals"], v["largest_output_tokens"], v["model_ids"]))
    assert trial.show(results) == 1
    printed = capsys.readouterr().out
    assert "STOP, decide before the run commit" in printed and "raise max_tokens to 1,024" in printed


def test_the_verdict_limits():
    rows = lambda latency, out: [{"error": None, "latency_s": latency, "output_tokens": out, "model_id": "m",
                                  "stop_reason_derived": "end_turn"}]
    settings = type("S", (), {"max_tokens": 512, "model": "m"})
    assert trial.verdicts(rows(10, 256), settings)["p99_latency_s"]["pass"]
    assert not trial.verdicts(rows(10.01, 256), settings)["p99_latency_s"]["pass"]
    assert trial.verdicts(rows(1, 256), settings)["largest_output_tokens"]["pass"]
    assert not trial.verdicts(rows(1, 257), settings)["largest_output_tokens"]["pass"]
    assert trial.p99(list(range(1, 101))) == 99 and trial.p99([3, 1, 2]) == 3


def test_the_trial_output_must_lie_outside_the_repository(model_config):
    with pytest.raises(ValueError, match="outside the repository"):
        trial.trial(REPO.joinpath("t07-trial-out"), model_config)


def test_the_trial_alerts_are_fresh_hand_written_alerts_in_the_world_format():
    assert len(ALERTS) >= 20 and len({a["id"] for a in ALERTS}) == len(ALERTS)
    ids = [item["id"] for a in ALERTS for item in a["evidence"]]
    assert len(set(ids)) == len(ids)
    for alert in ALERTS:
        build_payload(alert["evidence"])  # the agent's own payload check
        assert all(set(item) == {"id", "as_of_date", "source", "version", "kind", "field", "value"}
                   for item in alert["evidence"])
    actions = [a["expected_action"] for a in ALERTS]
    assert actions.count("ESCALATE") >= 3 and actions.count("CLOSE") >= 3
    families = " ".join(a["family"] for a in ALERTS)
    for family in ("plain", "name variant", "common name", "thin identifiers", "PEP", "conflicts", "injection",
                   "true match", "ambiguous"):
        assert family in families
    # nothing taken from the frozen world: no name, ID number or note of the world's alerts appears here
    world = {item["value"] for alert in load_alerts() for item in alert["evidence"]
             if item["field"] in ("name", "alias", "id_number", "snippet")}
    ours = {item["value"] for a in ALERTS for item in a["evidence"] if item["field"] in ("name", "alias", "id_number", "snippet")}
    assert not world & ours
