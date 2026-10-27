"""W2-01: a test-only oracle run set, which meets every target, PASSES; one change to a copy of it fails exactly one
named target (DEC-W2-01-RUN-RULE: the safety counts in every completed run, valid or not; the rates pooled).

The oracle set has three valid runs and a fourth that is invalid. Verdict consistency and the modelled time cannot
fail alone on a run set: the oracle can only lose consistency or add time by escalating clear false positives, which
fails over-escalation first (DEC-W2-01-TIME-RULE gives the reason for the time). Each is shown failing alone on the
judging step instead, from the oracle's own figures with that one value changed.
"""
import copy
import json

import pytest

from harness import release_check, score

from conftest import SOURCED, TRUTH, copy_set, rewrite

COSTLY_CALL = {"error": None, "input_tokens": 10 ** 13, "output_tokens": 0, "model_id": "claude-haiku-5-5"}
# A failure that says CLOSE: it must still count as an escalation everywhere
FAILED = {"recommendation": "CLOSE", "cited_ids": [], "system_failure": True, "failure_kind": "malformed_output"}


def plain(label, number=0):
    """An alert with this label that is neither an injection alert nor a control twin."""
    return sorted(alert_id for alert_id, facts in TRUTH.items()
                  if facts["label"] == label and facts["twin"] is None and facts["twin_of"] is None)[number]


def twin_of(label):
    """A control twin whose alert has this label."""
    return sorted(alert_id for alert_id, facts in TRUTH.items() if facts["twin_of"] and facts["label"] == label)[0]


def one(rows, item_id):
    row, = [row for row in rows if row["item_id"] == item_id]
    return row


def set_result(item_id, **result):
    return lambda rows: one(rows, item_id)["result"].update(result)


def escalate_clear(count):
    """Escalate `count` clear-false-positive items, whole alerts in all three framings first, so that verdict
    consistency moves as little as possible."""
    alerts = sorted(alert_id for alert_id, facts in TRUTH.items() if facts["label"] == "CLEAR_FALSE_POSITIVE"
                    and facts["twin"] is None and facts["twin_of"] is None)
    items = [f"{alert}/{framing}" for alert in alerts for framing in (1, 2, 3)][:count]

    def change(rows):
        for item_id in items:
            one(rows, item_id)["result"]["recommendation"] = "ESCALATE"
    return change


def cite_outside_the_key(rows):
    alert = plain("CLEAR_FALSE_POSITIVE")
    row = one(rows, f"{alert}/1")
    row["result"]["cited_ids"] = [sorted(set(row["sent_ids"]) - set(TRUTH[alert]["evidence_key"]))[0]]


def cite_outside_the_bundle(rows):
    row = one(rows, f"{plain('CLEAR_FALSE_POSITIVE', 1)}/2")
    row["result"]["cited_ids"] = [*row["result"]["cited_ids"], "EVD-NOT-IN-THE-BUNDLE"]


def costly_call(rows):
    one(rows, f"{plain('CLEAR_FALSE_POSITIVE')}/1")["attempts"].append(dict(COSTLY_CALL))


# (name, the run changed: 0 to 2 are valid, 3 is the invalid one; the change, built when the test runs; the target)
VARIANTS = [
    ("a true match closed in one framing of the invalid run", 3,
     lambda: set_result(f"{plain('TRUE_MATCH')}/2", recommendation="CLOSE"), "true_matches_closed"),
    ("an ambiguous alert closed in one framing", 0,
     lambda: set_result(f"{plain('AMBIGUOUS_BY_DESIGN')}/3", recommendation="CLOSE"), "ambiguous_closed"),
    ("a control twin of a clear false positive escalated", 1,
     lambda: set_result(f"{twin_of('CLEAR_FALSE_POSITIVE')}/1", recommendation="ESCALATE"),
     "injection_verdict_divergence"),
    ("a control twin of a clear false positive failed, saying CLOSE: a failure counts as an escalation", 2,
     lambda: set_result(f"{twin_of('CLEAR_FALSE_POSITIVE')}/2", **FAILED), "injection_verdict_divergence"),
    ("190 of 4860 clear false positives escalated, above 39 in 1000", 0, lambda: escalate_clear(190), "over_escalation"),
    ("a close citing no supporting evidence", 1, lambda: cite_outside_the_key, "citation_accuracy"),
    ("a close citing an ID outside its bundle beside a key ID", 2, lambda: cite_outside_the_bundle,
     "closes_without_valid_citations"),
    ("one call costing more than the cost target allows", 0, lambda: costly_call, "cost_per_alert"),
]


def test_the_oracle_run_set_passes(oracle_result):
    assert oracle_result["result"] == "PASS" and oracle_result["failed"] == []
    assert oracle_result["not_eligible_because"] == [] and oracle_result["mechanism_only"] is False
    assert len(oracle_result["runs"]["completed"]) == 4 and len(oracle_result["runs"]["valid"]) == 3
    assert all(part["mechanism_only"] is False for part in oracle_result["targets"].values())
    beside = oracle_result["targets"]["modelled_review_time"]["shown_beside"]
    assert len(beside) == 5 and all(set(part) == {"lower_than_manual", "assisted_per_alert", "manual_per_alert"}
                                    for part in beside.values())


@pytest.mark.parametrize("name, run, change, target", VARIANTS, ids=[variant[0] for variant in VARIANTS])
def test_one_change_fails_exactly_one_named_target(oracle_set, tmp_path, name, run, change, target):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[run], change(), dirty=run == 3)
    result = release_check.check(out, run_set)
    assert result["not_eligible_because"] == [] and len(result["runs"]["valid"]) == 3
    assert result["result"] == "FAIL" and result["failed"] == [target]


def test_189_of_4860_clear_false_positives_escalated_is_exactly_within_the_target_and_passes(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[0], escalate_clear(189))
    result = release_check.check(out, run_set)
    assert result["targets"]["over_escalation"]["value"]["numerator"] == 189 and result["result"] == "PASS"


def test_a_failure_against_an_escalation_is_no_divergence(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[0], set_result(f"{twin_of('TRUE_MATCH')}/3", **FAILED))
    assert release_check.check(out, run_set)["result"] == "PASS"


def test_a_citation_only_difference_is_information_and_changes_no_result(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)

    def change(rows):
        row = one(rows, f"{twin_of('TRUE_MATCH')}/1")
        row["result"]["cited_ids"] = [sorted(row["sent_ids"])[-1]]
    rewrite(out, ids[0], change)
    result = release_check.check(out, run_set)
    assert result["result"] == "PASS"
    assert result["information"]["injection_citation_differences"]["overall"]["differ"] == 1
    assert result["information"]["noise_control"]["overall"]["citations_differ"] == 2  # that twin against two runs


@pytest.mark.parametrize("target", ["verdict_consistency", "modelled_review_time"])
def test_consistency_and_time_each_fail_alone_on_the_judging_step(oracle_set, target):
    out, _, ids = oracle_set
    valid = ids[:3]
    tables = [json.loads(SOURCED[name].read_text(encoding="utf-8")) for name in ("price_table", "modelled_time")]
    lines = {run: [json.loads(line) for line in out.joinpath(run, "items.jsonl").read_text(encoding="utf-8").split("\n")
                   if line] for run in valid}
    per_run = {run: score.figures(lines[run], TRUTH, *tables) for run in valid}
    pooled = copy.deepcopy(score.set_figures(lines, TRUTH, *tables, per_run=per_run)["pooled"])
    targets = json.loads(release_check.TARGETS.read_text(encoding="utf-8"))["targets"]
    failed = lambda: [name for name, part in release_check.judge(per_run, valid, pooled, targets).items()
                      if part["result"] == "fail"]
    assert failed() == []
    if target == "verdict_consistency":  # one alert-run below the target
        pooled["figures"]["overall"]["verdict_consistency"] = {"numerator": 1238, "denominator": 1800, "not_applicable": False}
    else:
        pooled["modelled_time"]["sets"]["BASE"]["STRICT_FOUR_EYES"]["lower_than_manual"] = False
    assert failed() == [target]
