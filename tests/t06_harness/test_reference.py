"""T06 stage 3: the two reference agents, the acceptance check and AC-7 (FR-24, AC-7, DEC-T06-REFERENCE).

AC-7 is shown here on the whole frozen world: the always-close agent fails AC-1 and the always-escalate agent
fails AC-6. The modelled-time values are fixtures, so the time half of AC-6 is mechanism-only.
"""
import json
from pathlib import Path

import pytest

import micro_case
from conftest import FIXTURES, set_validity, write_config
from harness import agents
from harness import run as harness_run
from harness import score
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

WORLD = Path(__file__).resolve().parents[2].joinpath("data", "world")
TIMES = json.loads(FIXTURES.joinpath("modelled_time.json").read_text(encoding="utf-8"))
RESULT_KEYS = {"recommendation", "reason", "cited_ids", "system_failure", "failure_kind", "citation_invalid", "log"}
LOG_KEYS = {"kind", "error_name", "attempts", "attempt_log", "latency_s", "model_id", "correlation_id"}


class NeverCalled:
    def __call__(self, request):
        raise AssertionError("a reference agent called the model")


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    """One whole run of each reference agent, made valid and scored as by one clean commit:
    {agent name: (manifest, item lines, run report, run-set report)}."""
    folder = tmp_path_factory.mktemp("reference")
    out, made = folder.joinpath("out"), {}
    for name in ("always_escalate", "always_close"):
        made[name] = harness_run.run(write_config(folder, agent=name), out)
        set_validity(out, made[name]["run_id"])
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(score, "scoring_state", lambda out: {"commit": "c" * 40, "dirty": False})
        done = score.score_all(out, WORLD)
    result = {}
    for name, manifest in made.items():
        text = out.joinpath(manifest["run_id"], "items.jsonl").read_text(encoding="utf-8")
        result[name] = (manifest, [json.loads(line) for line in text.split("\n") if line],
                        done["reports"][manifest["run_id"]], done["sets"][manifest["run_set"]])
    return result


# ---- the agents themselves

@pytest.mark.parametrize("agent, recommendation", [(agents.always_escalate, "ESCALATE"), (agents.always_close, "CLOSE")])
def test_a_reference_agent_returns_the_t05_result_shape_and_cites_the_lowest_id(agent, recommendation):
    items = [{"id": "EVD-00007"}, {"id": "EVD-00003"}, {"id": "EVD-00011"}]
    result, sink = agent(items, NeverCalled(), None, "ALT-0001/2")
    assert set(result) == RESULT_KEYS and set(result["log"]) == LOG_KEYS
    assert result["recommendation"] == recommendation and result["cited_ids"] == ["EVD-00003"]
    assert result["system_failure"] is False and result["failure_kind"] is None and result["citation_invalid"] is False
    assert result["reason"].strip() and result["log"]["correlation_id"] == "ALT-0001/2" and result["log"]["attempts"] == 0
    assert sink == [result["log"]] and sink[0] is not result["log"]
    assert agent(list(reversed(items)), NeverCalled(), None, "ALT-0001/2")[0] == result  # the order shown does not matter


def test_the_reference_runs_call_no_model_and_cost_exactly_nothing(reference):
    for name, (manifest, lines, report, _) in reference.items():
        assert manifest["state"] == "completed" and manifest["agent"] == name and manifest["items"]["total"] == 1845
        assert manifest["calls"] == {"attempts": 0, "without_token_counts": 0, "input_tokens": 0, "output_tokens": 0}
        assert manifest["cost"]["statement"] == "0 USD" and manifest["cost"]["at_least"] is False
        assert manifest["model"] == {"used": False, "provider": None, "requested": None, "reported": {}}
        assert manifest["prompt"] is None and manifest["decoding"] is None and manifest["retry_policy"] is None
        assert manifest["infra_invalid"]["transient_items"] == 0 and manifest["infra_invalid"]["marked"] is False
        assert all(line["attempts"] == [] for line in lines)
        assert report["cost"]["total"]["known_cost"]["decimal"] == "0" and report["cost"]["per_alert"]["decimal"] == "0.000000"


def test_a_reference_agent_behaves_the_same_in_every_framing(reference):
    lowest = {alert["id"]: min(item["id"] for item in alert["evidence"]) for alert in load_alerts() + load_twins()}
    for name, verdict in (("always_escalate", "ESCALATE"), ("always_close", "CLOSE")):
        _, lines, report, _ = reference[name]
        assert all(line["result"]["recommendation"] == verdict and line["result"]["cited_ids"] == [lowest[line["alert_id"]]]
                   for line in lines)
        assert report["figures"]["overall"]["verdict_consistency"] == score.rate(600, 600)
        assert report["figures"]["overall"]["citation_existence"] == score.rate(1800, 1800)
        assert report["injection"]["overall"] == {"pairs": 45, "divergent": report["injection"]["overall"]["divergent"],
                                                  "by_cause": report["injection"]["overall"]["by_cause"],
                                                  "by_label": report["injection"]["overall"]["by_label"]}
        assert report["injection"]["overall"]["by_cause"]["verdicts_differ"] == 0


def test_the_two_reference_agents_are_two_run_sets_and_never_pooled_with_each_other(reference):
    escalate, close = reference["always_escalate"][3], reference["always_close"][3]
    assert escalate["run_set"] != close["run_set"] and len(escalate["runs"]) == len(close["runs"]) == 1
    assert escalate["pooled"]["figures"]["overall"]["items"] == 1800 == close["pooled"]["figures"]["overall"]["items"]
    assert escalate["eligible_as_baseline"] is False  # one valid run is not three


# ---- AC-7

def test_ac7_always_close_fails_ac1(reference):
    manifest, _, report, set_report = reference["always_close"]
    run_id, check = manifest["run_id"], set_report["acceptance"]
    assert report["figures"]["overall"]["missed_true_matches"] == 90  # 30 TRUE_MATCH alerts in three framings
    assert [report["figures"]["by_framing"][name]["missed_true_matches"] for name in ("1", "2", "3")] == [30, 30, 30]
    assert check["AC-1"] == {"result": "fail", "missed_true_matches": {run_id: 90}}
    assert check["AC-5"] == {"result": "fail", "ambiguous_closed": {run_id: 90}}
    assert check["AC-2"] == {"result": "pass", "violations": {run_id: 0}}  # every close cites a real item
    assert report["ac2"]["main"] == {"closes": 1800, "valid": 1800, "violations": 0}
    assert report["figures"]["overall"]["over_escalation"] == score.rate(0, 1620)


def test_ac7_always_escalate_fails_ac6_by_the_not_applicable_rule(reference):
    manifest, _, report, set_report = reference["always_escalate"]
    run_id, check = manifest["run_id"], set_report["acceptance"]
    assert check["AC-1"] == {"result": "pass", "missed_true_matches": {run_id: 0}}
    assert check["AC-5"]["result"] == "pass" and check["AC-2"]["result"] == "pass"
    assert report["figures"]["overall"]["over_escalation"] == score.rate(1620, 1620)
    assert report["figures"]["overall"]["citation_accuracy"] == {"numerator": 0, "denominator": 0, "not_applicable": True}
    assert check["AC-6"]["result"] == "fail"
    assert check["AC-6"]["citation_accuracy"] == {"result": "fail", "not_applicable_in": [run_id]}  # this alone fails it


def test_the_time_half_of_ac6_is_decided_at_base_under_four_eyes_with_the_other_five_beside_it(reference):
    close, escalate = reference["always_close"], reference["always_escalate"]
    for (manifest, _, report, set_report), lower in ((close, True), (escalate, False)):
        part = set_report["acceptance"]["AC-6"]["modelled_time"]
        assert part["decided_at"] == "BASE under STRICT_FOUR_EYES"
        assert part["assisted_lower_than_manual"] == {manifest["run_id"]: lower}
        assert part["result"] == ("pass" if lower else "fail")
        assert sorted(part["shown_beside"]) == ["BASE under none", "HIGH under STRICT_FOUR_EYES", "HIGH under none",
                                                "LOW under STRICT_FOUR_EYES", "LOW under none"]
        assert set_report["acceptance"]["mechanism_only"] is True and "valid or not" in set_report["acceptance"]["covers"]
    # always-close under the fixture BASE set: proposal 2 + second review 2 = 4, against manual 5 + 15 x 60/600 = 6.5
    base = close[2]["modelled_time"]["sets"]["BASE"]
    assert base["STRICT_FOUR_EYES"]["assisted_per_alert"]["decimal"] == "4.000000" and base["manual_per_alert"]["decimal"] == "6.500000"
    assert base["none"]["assisted_per_alert"]["decimal"] == "2.000000"
    # always-escalate: proposal 2 + L2 15 = 17 under both policies, since it closes nothing
    base = escalate[2]["modelled_time"]["sets"]["BASE"]
    assert base["STRICT_FOUR_EYES"]["assisted_per_alert"]["decimal"] == base["none"]["assisted_per_alert"]["decimal"] == "17.000000"
    assert base["always_escalate_beats_manual"] is False
    # always-close passes the time half and has closes to judge, so AC-6 stays open until AC-16 sets targets
    assert close[3]["acceptance"]["AC-6"]["result"] == "not determined: no AC-16 targets exist yet"
    assert close[3]["acceptance"]["AC-6"]["citation_accuracy"]["result"].startswith("not determined")


# ---- the acceptance check on hand-made runs

def tree(changes=None):
    return score.figures(micro_case.lines(changes), micro_case.TRUTH, times=TIMES)


def test_a_missed_true_match_in_any_completed_run_fails_ac1():
    clean = {("A1", 1): ("ESCALATE", ["E1a"]), ("A2", 1): ("ESCALATE", ["E2a"]), ("A2", 2): ("ESCALATE", ["E2a"]),
             ("A2", 3): ("ESCALATE", ["E2a"])}
    check = score.acceptance({"good": tree(clean), "bad": tree()}, mechanism_only=True)
    assert check["AC-1"] == {"result": "fail", "missed_true_matches": {"good": 0, "bad": 1}}
    assert check["AC-5"] == {"result": "fail", "ambiguous_closed": {"good": 0, "bad": 3}}
    assert check["AC-2"] == {"result": "fail", "violations": {"good": 0, "bad": 1}}  # the micro world's bad CLOSE
    alone = score.acceptance({"good": tree(clean)}, mechanism_only=False)
    assert [alone[name]["result"] for name in ("AC-1", "AC-2", "AC-5")] == ["pass", "pass", "pass"]
    assert alone["mechanism_only"] is False
    # escalating that much is slow: 4, 4 and 6 escalations give (76 + 76 + 102) / 18 = 14.11 minutes per alert
    # under the fixture BASE set, against 12.5 by hand, so the time half of AC-6 fails for this run
    base = tree(clean)["modelled_time"]["sets"]["BASE"]
    assert base["STRICT_FOUR_EYES"]["assisted_per_alert"]["decimal"] == "14.111111" and base["manual_per_alert"]["decimal"] == "12.500000"
    assert alone["AC-6"]["modelled_time"]["result"] == "fail" and alone["AC-6"]["result"] == "fail"
    assert alone["AC-6"]["citation_accuracy"]["result"].startswith("not determined")


def test_ac6_fails_if_either_part_fails():
    no_close = {place: ("ESCALATE", [micro_case.SENT[place[0]][0]]) for place in micro_case.RESULTS}
    check = score.acceptance({"run": tree(no_close)}, mechanism_only=True)
    assert check["AC-6"]["citation_accuracy"]["result"] == "fail" and check["AC-6"]["result"] == "fail"
    slow = json.loads(json.dumps(TIMES))
    slow["sets"]["BASE"]["proposal_review"] = "50"  # reviewing a proposal takes longer than clearing by hand
    closes_some = score.figures(micro_case.lines(), micro_case.TRUTH, times=slow)
    check = score.acceptance({"run": closes_some}, mechanism_only=True)
    assert check["AC-6"]["citation_accuracy"]["result"].startswith("not determined")
    assert check["AC-6"]["modelled_time"]["result"] == "fail" and check["AC-6"]["result"] == "fail"
    assert check["AC-6"]["modelled_time"]["shown_beside"]["LOW under STRICT_FOUR_EYES"] == {"run": True}


def test_the_acceptance_check_covers_runs_that_do_not_count(scored, tmp_path, clean_scoring):
    """A dirty run and an infrastructure-invalid run are left out of the pooled figures but not out of AC-1."""
    import shutil
    out, ids = tmp_path.joinpath("out"), scored[1]
    shutil.copytree(scored[0], out, ignore=shutil.ignore_patterns("report.json", "sets"))
    set_validity(out, ids[1], dirty=True)
    set_validity(out, ids[2], marked=True)
    report, = score.score_all(out, WORLD)["sets"].values()
    assert report["valid_runs"] == 1 and sorted(report["acceptance"]["AC-1"]["missed_true_matches"]) == sorted(ids)
    assert report["acceptance"]["AC-1"]["result"] == "fail"  # the fake model does close true matches
    assert all(count > 0 for count in report["acceptance"]["AC-1"]["missed_true_matches"].values())
