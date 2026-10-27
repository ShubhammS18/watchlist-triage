"""W2-01: the committed baseline, run set f2e614d2, judged by the release check. It must FAIL for exactly the known
reasons, reproduce the injection and noise-control counts of DEC-W2-AC12-RULE, and leave baseline/ untouched. Re-scoring
it with the new code must give the old figures unchanged (DEC-W2-01-DESIGN)."""
import json
import subprocess

import pytest

from harness import release_check, score
from harness.manifest import REPO

from conftest import TRUTH

BASELINE = REPO.joinpath("baseline")
RUN_SET = "f2e614d2d530dc65c1d9f4dbec452d93296f5f52420b0f7829ff4404e7a99305"
RUNS = ("20261021T071953083777Z-f2e614d2", "20261021T074456632955Z-f2e614d2", "20261021T080418874378Z-f2e614d2")
NEW_INJECTION_KEYS = ("verdict_divergence", "citation_differences")


@pytest.fixture(scope="module")
def result():
    before = subprocess.run(["git", "status", "--porcelain", "--", "baseline"], cwd=REPO, capture_output=True, text=True)
    done = release_check.check(BASELINE, RUN_SET)
    after = subprocess.run(["git", "status", "--porcelain", "--", "baseline"], cwd=REPO, capture_output=True, text=True)
    assert before.stdout == after.stdout == ""
    assert subprocess.run(["sha256sum", "--check", "--quiet", "SHA256SUMS"], cwd=BASELINE).returncode == 0
    return done


def test_the_baseline_is_eligible_and_fails_for_exactly_the_known_reasons(result):
    assert result["not_eligible_because"] == [] and result["runs"]["valid"] == list(RUNS)
    assert result["result"] == "FAIL"
    assert result["failed"] == ["ambiguous_closed", "injection_verdict_divergence", "modelled_review_time",
                                "over_escalation", "true_matches_closed"]


def test_the_baseline_counts_and_rates(result):
    targets = result["targets"]
    assert targets["true_matches_closed"]["per_run"] == dict.fromkeys(RUNS, 1)
    assert targets["ambiguous_closed"]["per_run"] == {RUNS[0]: 0, RUNS[1]: 0, RUNS[2]: 1}
    assert sum(targets["injection_verdict_divergence"]["per_run"].values()) == 14
    assert targets["closes_without_valid_citations"]["per_run"] == dict.fromkeys(RUNS, 0)
    value = lambda name: (targets[name]["value"]["numerator"], targets[name]["value"]["denominator"])
    assert value("over_escalation") == (2562, 4860)
    assert value("verdict_consistency") == (1239, 1800) and targets["verdict_consistency"]["result"] == "pass"
    assert value("citation_accuracy") == (2298, 2298) and targets["citation_accuracy"]["result"] == "pass"
    assert value("cost_per_alert") == (3371461, 18000000000) and targets["cost_per_alert"]["result"] == "pass"
    assert targets["modelled_review_time"]["assisted_per_alert"]["decimal"] == "71.697037"


def test_the_injection_figures_and_the_noise_control_match_the_ac12_record(result):
    information = result["information"]
    assert information["injection_verdict_divergence"]["overall"] == {"pairs": 135, "differ": 14}
    noise = information["noise_control"]
    assert noise["runs"] == 3 and noise["overall"] == {"comparisons": 135, "verdicts_differ": 0, "citations_differ": 40}
    for tree in (information["injection_verdict_divergence"], information["injection_citation_differences"]):
        for part in ("by_framing", "by_label", "by_family"):  # each breakdown on its own adds up to the whole
            assert sum(block["pairs"] for block in tree[part].values()) == tree["overall"]["pairs"]
            assert sum(block["differ"] for block in tree[part].values()) == tree["overall"]["differ"]


def without_new(tree):
    """A figures tree as the old code wrote it: the new injection keys left out."""
    tree = json.loads(json.dumps(tree))
    for key in NEW_INJECTION_KEYS:
        tree["injection"].pop(key, None)
    return tree


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


@pytest.fixture(scope="module")
def rescored():
    loaded = {}
    for run in RUNS:
        manifest = json.loads(BASELINE.joinpath(run, "manifest.json").read_text(encoding="utf-8"))
        lines = [json.loads(line) for line in BASELINE.joinpath(run, "items.jsonl").read_text(encoding="utf-8").split("\n") if line]
        loaded[run] = (manifest, lines)
    tables = (loaded[RUNS[0]][0]["price_table"]["table"], loaded[RUNS[0]][0]["modelled_time"]["parameters"])
    per_run = {run: score.figures(lines, TRUTH, *tables) for run, (_, lines) in loaded.items()}
    return per_run, score.set_figures({run: lines for run, (_, lines) in loaded.items()}, TRUTH, *tables, per_run=per_run)


@pytest.mark.parametrize("run", RUNS)
def test_rescoring_a_baseline_run_gives_its_committed_figures_byte_for_byte(rescored, run):
    committed = json.loads(BASELINE.joinpath(run, "report.json").read_text(encoding="utf-8"))
    new = without_new(rescored[0][run])
    assert set(new) == {"figures", "cost", "modelled_time", "ac2", "twins", "injection"}
    for key in new:
        assert canonical(new[key]) == canonical(committed[key]), key


def test_rescoring_the_baseline_set_gives_its_committed_pooled_figures_and_spread_byte_for_byte(rescored):
    committed = json.loads(BASELINE.joinpath("sets", f"{RUN_SET}.json").read_text(encoding="utf-8"))
    assert canonical(without_new(rescored[1]["pooled"])) == canonical(committed["pooled"])
    assert canonical(without_new(rescored[1]["spread"])) == canonical(committed["spread"])
