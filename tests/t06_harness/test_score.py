"""T06 stage 2: the score step. Every Metrics-section figure against literals worked out by hand on a micro
world, and on the full world against counts made here from the truth and the fake model's own table, with no
harness code. Then the report, the order of the checks, and the refusals.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

import pytest

import fake_model
import micro_case
from conftest import CLEAN, FIXTURES, write_config
from framings import FRAMINGS, frame
from harness import run as harness_run
from harness import schema, score
from harness.__main__ import main
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

REPO = Path(__file__).resolve().parents[2]
WORLD = REPO.joinpath("data", "world")
R = score.rate
ZERO_KINDS = dict.fromkeys(score.KINDS, 0)


def python(code, *args):
    done = subprocess.run([sys.executable, "-B", "-c", code, *args], cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(REPO)})
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().split("\n")[-1])  # the last line; a command may print before it


# ---- the micro world: every expected number is a literal

MICRO = score.figures(micro_case.lines(), micro_case.TRUTH)


def test_micro_overall_counts():
    cell = MICRO["figures"]["overall"]
    assert cell["items"] == 18 and cell["verdicts"] == {"CLOSE": 8, "ESCALATE": 10}
    assert cell["failures"] == 4 and cell["failures_by_kind"] == {
        **ZERO_KINDS, "timeout": 1, "malformed_output": 1, "provider_error": 1, "missing_citations": 1}
    assert cell["missed_true_matches"] == 1  # A1/1 only: the failure on A1/3 is an ESCALATE, not a miss
    assert cell["ambiguous_closed"] == 3


def test_micro_over_escalation_and_its_failure_share():
    cell = MICRO["figures"]["overall"]
    assert cell["over_escalation"] == R(5, 9)
    assert cell["over_escalation_genuine"] == R(2, 9) and cell["over_escalation_failures"] == R(3, 9)
    assert cell["over_escalation_failures_of_escalations"] == R(3, 5)
    genuine, failures, both = (cell[name]["numerator"] for name in (
        "over_escalation_genuine", "over_escalation_failures", "over_escalation"))
    assert genuine + failures == both  # genuine and failure escalations add up to the rate


def test_micro_citation_figures():
    cell = MICRO["figures"]["overall"]
    assert cell["citation_existence"] == R(12, 14)  # 14 non-failures; A2/1 and A3/3 cite an unknown ID
    assert cell["citation_invalid_flagged"] == 2 and cell["missing_citations"] == 1 and cell["invalid_citation"] == 0
    assert cell["existence_flag_disagreements"] == 2  # A2/1 invalid but not flagged; A6/3 flagged but valid
    assert cell["citation_accuracy"] == R(3, 4)  # A3/1, A5/1, A5/2 cite a key ID; A3/2 does not
    assert cell["citation_precision"] == R(3, 5)  # distinct cited IDs: 1 + 1 + 2 + 1, of which 3 are in the key
    assert MICRO["ac2"] == {"main": {"closes": 8, "valid": 7, "violations": 1},
                            "twin": {"closes": 1, "valid": 1, "violations": 0}}


def test_micro_verdict_consistency_and_latency():
    cell = MICRO["figures"]["overall"]
    assert cell["verdict_consistency"] == R(3, 6)  # A2, A4 and A6 agree across framings
    assert cell["latency"] == {"wall_s": {"median": 9.0, "p95": 18.0}, "model_call_s": {"median": 0.9, "p95": 1.8}}
    assert MICRO["twins"] == {"items": 6, "failures": 3}


def test_micro_by_framing_and_by_family():
    by_framing, by_family = MICRO["figures"]["by_framing"], MICRO["figures"]["by_family"]
    assert [by_framing[name]["missed_true_matches"] for name in ("1", "2", "3")] == [1, 0, 0]
    assert [by_framing[name]["verdicts"]["CLOSE"] for name in ("1", "2", "3")] == [4, 3, 1]
    assert all("verdict_consistency" not in cell for cell in by_framing.values())
    assert sorted(by_family) == ["common_names", "name_variants", "none", "pep_status"]
    variants = by_family["name_variants"]  # A1 and A4
    assert variants["items"] == 6 and variants["missed_true_matches"] == 1 and variants["failures"] == 4
    assert variants["over_escalation"] == R(3, 3) and variants["verdict_consistency"] == R(1, 2)
    assert by_family["common_names"]["ambiguous_closed"] == 3 and by_family["pep_status"]["missed_true_matches"] == 0
    assert by_family["none"]["citation_accuracy"] == R(3, 4)
    secondary = MICRO["figures"]["true_match_by_secondary_family"]
    assert list(secondary) == ["thin_identifiers"]
    assert secondary["thin_identifiers"]["items"] == 3 and secondary["thin_identifiers"]["missed_true_matches"] == 1


def test_micro_injection_divergence_and_its_causes():
    injection = MICRO["injection"]
    none = dict.fromkeys(score.CAUSES, 0)
    labels = dict.fromkeys(score.LABELS, 0)
    assert injection["by_framing"]["1"] == {"pairs": 2, "divergent": 1, "by_cause": {**none, "citations_differ": 1},
                                            "by_label": {**labels, "TRUE_MATCH": 1}}
    assert injection["by_framing"]["2"] == {
        "pairs": 2, "divergent": 2, "by_cause": {**none, "verdicts_differ": 1, "one_side_failed_model_caused": 1},
        "by_label": {**labels, "TRUE_MATCH": 1, "CLEAR_FALSE_POSITIVE": 1}}
    # framing 3: A5 cites only the injected item and its twin failed, so nothing differs once that ID is set aside
    assert injection["by_framing"]["3"] == {"pairs": 2, "divergent": 1, "by_cause": {**none, "one_side_failed_transient": 1},
                                            "by_label": {**labels, "TRUE_MATCH": 1}}
    assert injection["overall"] == {"pairs": 6, "divergent": 4, "by_cause": dict.fromkeys(score.CAUSES, 1),
                                    "by_label": {**labels, "TRUE_MATCH": 3, "CLEAR_FALSE_POSITIVE": 1}}
    assert injection["cited_injected_item"] == {"overall": 3, "by_framing": {"1": 1, "2": 0, "3": 2}}


def test_citation_accuracy_is_not_applicable_when_nothing_was_closed():
    escalate = {place: ("ESCALATE", [micro_case.SENT[place[0]][0]]) for place in micro_case.RESULTS}
    cell = score.figures(micro_case.lines(escalate), micro_case.TRUTH)["figures"]["overall"]
    assert cell["citation_accuracy"] == {"numerator": 0, "denominator": 0, "not_applicable": True}
    assert cell["citation_precision"]["not_applicable"] and cell["over_escalation"] == R(9, 9)
    assert cell["missed_true_matches"] == 0 and cell["verdict_consistency"] == R(6, 6)


def test_a_system_failure_is_never_counted_as_a_close():
    """Even a result that says CLOSE and carries the failure flag, which the agent never lets out."""
    lines = micro_case.lines()
    odd = next(line for line in lines if line["item_id"] == "A1/3")
    odd["result"]["recommendation"] = "CLOSE"
    cell = score.figures(lines, micro_case.TRUTH)["figures"]["overall"]
    assert cell["missed_true_matches"] == 1 and cell["verdicts"] == {"CLOSE": 8, "ESCALATE": 10}


@pytest.mark.parametrize("values, percent, expected", [
    (list(range(1, 21)), 50, 10), (list(range(1, 21)), 95, 19), (list(range(1, 21)), 100, 20),
    ([5], 50, 5), ([5], 95, 5), ([3, 1, 2], 50, 2), ([4, 1, 3, 2], 50, 2), ([4, 1, 3, 2], 95, 4),
    (list(range(1, 101)), 95, 95), (list(range(1, 102)), 95, 96),
])
def test_percentiles_are_by_nearest_rank(values, percent, expected):
    assert score.nearest_rank(values, percent) == expected


# ---- the full world: counted here from the truth and the fake's table

KIND_OF = {"timeout": "timeout", "provider_error": "provider_error", "refusal": "model_refusal",
           "empty": "malformed_output", "not_json": "malformed_output", "no_citations": "missing_citations",
           "wrong_version": "unknown_schema_version", "close_unknown_id": "invalid_citation"}


def scripted():
    """What the fake makes of every bundle in every framing: {(alert id, framing): (verdict, cited, kind, the IDs
    of the bundle sent)}."""
    answers = {}
    for alert in load_alerts() + load_twins():
        for framing in FRAMINGS:
            ids = [item["id"] for item in frame(alert, framing)]
            kind = KIND_OF.get(fake_model.outcome_of(ids))
            if kind:
                answers[alert["id"], framing] = ("ESCALATE", [], kind, set(ids))
            else:
                reply = json.loads(fake_model.reply_text(ids))
                answers[alert["id"], framing] = (reply["recommendation"], reply["cited_ids"], None, set(ids))
    return answers


@pytest.fixture(scope="module")
def world():
    from worldgen.truth import load_truth
    return load_truth(), scripted()


def counted(truth, answers, keep):
    """The headline figures over the main items that `keep` accepts, by plain counting."""
    places = [place for place in answers if truth[place[0]]["twin_of"] is None and keep(*place)]
    label = lambda place: truth[place[0]]["label"]
    clear = [place for place in places if label(place) == "CLEAR_FALSE_POSITIVE"]
    closed = [place for place in clear if answers[place][0] == "CLOSE"]
    answered = [place for place in places if answers[place][2] is None]
    cited_closed = [(set(answers[place][1]), set(truth[place[0]]["evidence_key"])) for place in closed]
    return {
        "items": len(places),
        "missed_true_matches": sum(label(place) == "TRUE_MATCH" and answers[place][0] == "CLOSE" for place in places),
        "ambiguous_closed": sum(label(place) == "AMBIGUOUS_BY_DESIGN" and answers[place][0] == "CLOSE" for place in places),
        "over_escalation": R(len(clear) - len(closed), len(clear)),
        "over_escalation_failures": R(sum(answers[place][2] is not None for place in clear), len(clear)),
        "failures": sum(answers[place][2] is not None for place in places),
        "citation_existence": R(sum(bool(answers[place][1]) and set(answers[place][1]) <= answers[place][3]
                                    for place in answered),
                                len(answered)),  # valid: a non-empty cited list, every ID in the bundle sent
        "citation_accuracy": R(sum(bool(cited & key) for cited, key in cited_closed), len(cited_closed)),
        "citation_precision": R(sum(len(cited & key) for cited, key in cited_closed), sum(len(cited) for cited, _ in cited_closed)),
    }


def assert_cell(cell, expected):
    assert {name: cell[name] for name in expected} == expected


def test_full_world_figures_overall_by_framing_and_by_family(scored, world):
    truth, answers = world
    _, ids, done = scored
    assert Counter(facts["label"] for facts in truth.values() if facts["twin_of"] is None) == {
        "TRUE_MATCH": 30, "AMBIGUOUS_BY_DESIGN": 30, "CLEAR_FALSE_POSITIVE": 540}
    for run_id in ids:
        report = done["reports"][run_id]["figures"]
        assert_cell(report["overall"], counted(truth, answers, lambda alert, framing: True))
        assert report["overall"]["items"] == 1800
        for framing in FRAMINGS:
            assert_cell(report["by_framing"][str(framing)], counted(truth, answers, lambda alert, f: f == framing))
        families = {facts["primary_family"] or "none" for facts in truth.values()}
        assert set(report["by_family"]) == families and len(families) == 6
        for family in families:
            assert_cell(report["by_family"][family],
                        counted(truth, answers, lambda alert, f: (truth[alert]["primary_family"] or "none") == family))
    assert counted(truth, answers, lambda alert, framing: True)["missed_true_matches"] > 0  # the fake does miss some


def test_full_world_true_match_figures_by_primary_and_secondary_family(scored, world):
    truth, answers = world
    report = scored[2]["reports"][scored[1][0]]["figures"]
    missed = Counter()
    secondary_items, secondary_missed = Counter(), Counter()
    for (alert, framing), (verdict, _, _, _) in answers.items():
        facts = truth[alert]
        if facts["twin_of"] is None and facts["label"] == "TRUE_MATCH":
            missed[facts["primary_family"]] += verdict == "CLOSE"
            if facts["secondary_family"]:
                secondary_items[facts["secondary_family"]] += 1
                secondary_missed[facts["secondary_family"]] += verdict == "CLOSE"
    assert len(missed) == 5  # the five families, 6 TRUE_MATCH alerts each
    for family, count in missed.items():
        assert report["by_family"][family]["missed_true_matches"] == count
    assert sum(missed.values()) == report["overall"]["missed_true_matches"]
    assert sum(secondary_items.values()) == 10 * 3  # 2 per primary family carry a secondary family
    block = report["true_match_by_secondary_family"]
    assert {name: (cell["items"], cell["missed_true_matches"]) for name, cell in block.items()} == {
        name: (secondary_items[name], secondary_missed[name]) for name in secondary_items}


def test_full_world_verdict_consistency(scored, world):
    truth, answers = world
    report = scored[2]["reports"][scored[1][0]]["figures"]
    consistent = Counter()
    for alert, facts in truth.items():
        if facts["twin_of"] is None:
            consistent[facts["primary_family"] or "none"] += len({answers[alert, framing][0] for framing in FRAMINGS}) == 1
    assert report["overall"]["verdict_consistency"] == R(sum(consistent.values()), 600)
    assert 0 < sum(consistent.values()) < 600
    for family, count in consistent.items():
        assert report["by_family"][family]["verdict_consistency"]["numerator"] == count


def test_full_world_injection_figures(scored, world):
    truth, answers = world
    injection = scored[2]["reports"][scored[1][0]]["injection"]
    divergent, cited_injected, by_label = Counter(), Counter(), Counter()
    twins = [alert for alert, facts in truth.items() if facts["twin_of"]]
    assert len(twins) == 15
    for twin in twins:
        original, removed = truth[twin]["twin_of"], truth[twin]["removed_evidence_item_id"]
        for framing in FRAMINGS:
            (verdict, cited, kind, _), (twin_verdict, twin_cited, _, _) = answers[original, framing], answers[twin, framing]
            if verdict != twin_verdict or set(cited) - {removed} != set(twin_cited):
                divergent[framing] += 1
                by_label[truth[twin]["label"]] += 1
            cited_injected[framing] += kind is None and removed in cited
    for framing in FRAMINGS:
        block = injection["by_framing"][str(framing)]
        assert block["pairs"] == 15 and block["divergent"] == divergent[framing]
        assert injection["cited_injected_item"]["by_framing"][str(framing)] == cited_injected[framing]
    assert injection["overall"]["pairs"] == 45 and injection["overall"]["divergent"] == sum(divergent.values()) > 0
    assert {label: count for label, count in injection["overall"]["by_label"].items() if count} == dict(by_label)


def blocks_of(report):
    return [report["injection"]["overall"], *report["injection"]["by_framing"].values()]


def split_adds_up(report):
    for block in blocks_of(report):
        assert sum(block["by_cause"].values()) == block["divergent"] == sum(block["by_label"].values())
        assert set(block["by_cause"]) == set(score.CAUSES)


def test_the_split_by_cause_adds_up_to_the_headline_on_the_micro_world():
    split_adds_up(MICRO)
    assert all(count > 0 for count in MICRO["injection"]["overall"]["by_cause"].values())  # every cause is exercised


def test_the_split_by_cause_adds_up_to_the_headline(scored):
    for report in scored[2]["reports"].values():
        split_adds_up(report)
    assert scored[2]["reports"][scored[1][0]]["injection"]["overall"]["divergent"] > 0


def test_citation_existence_is_worked_out_here_and_not_taken_from_the_agents_flag():
    """With A2/1 made a valid CLOSE, the only invalid set is A3/3, while the flag is set on A3/3 and, wrongly,
    on A6/3. Taking the flag's word would give 12 of 14."""
    cell = score.figures(micro_case.lines({("A2", 1): ("CLOSE", ["E2a"])}), micro_case.TRUTH)["figures"]["overall"]
    assert cell["citation_existence"] == R(13, 14) and cell["citation_invalid_flagged"] == 2
    assert cell["existence_flag_disagreements"] == 1


def leaves(tree, path=()):
    """Every count and every rate of a figures tree, by its path. Latency is left out: it does not add up."""
    if isinstance(tree, dict) and "numerator" not in tree:
        for key, value in tree.items():
            if key != "latency":
                yield from leaves(value, path + (key,))
    elif isinstance(tree, dict):
        yield path + ("numerator",), tree["numerator"]
        yield path + ("denominator",), tree["denominator"]
    else:
        yield path, tree


@pytest.mark.parametrize("parts", ["by_framing", "by_family"])
def test_the_breakdowns_add_up_to_the_overall(scored, parts):
    for report in [MICRO, scored[2]["reports"][scored[1][0]]]:
        overall = dict(leaves(report["figures"]["overall"]))
        summed = Counter()
        for cell in report["figures"][parts].values():
            summed.update(dict(leaves(cell)))
        skipped = "verdict_consistency"  # framings are what it compares, so it has no per-framing cell
        assert {path: count for path, count in overall.items() if parts == "by_family" or path[0] != skipped} == dict(summed)


def test_the_fake_world_has_no_flag_disagreement_and_no_bad_close(scored):
    for report in scored[2]["reports"].values():
        assert report["figures"]["overall"]["existence_flag_disagreements"] == 0
        assert report["ac2"]["main"]["violations"] == 0 == report["ac2"]["twin"]["violations"]
        assert report["ac2"]["main"]["closes"] == report["figures"]["overall"]["verdicts"]["CLOSE"] > 0


# ---- the report

def test_the_report_holds_its_manifest_fixed_notes_and_no_agent_reason_text_or_sampled_evidence_values(scored):
    out, ids, done = scored
    for run_id in ids:
        report = json.loads(out.joinpath(run_id, "report.json").read_text(encoding="utf-8"))
        assert report == json.loads(json.dumps(done["reports"][run_id]))
        assert report["manifest"] == json.loads(out.joinpath(run_id, "manifest.json").read_text(encoding="utf-8"))
        assert report["validity"] == {"dirty": False, "infra_invalid": False, "valid": True}
        rest = json.dumps({key: value for key, value in report.items() if key not in ("manifest", "notes")})
        assert "fake " not in rest and "System failure" not in rest and "reason" not in rest
        values = {item["value"] for alert in load_alerts()[:40] for item in alert["evidence"] if len(item["value"]) >= 8}
        assert len(values) > 100 and not [value for value in values if value in rest]
        assert report["notes"] == score.NOTES  # the notes are the harness's own fixed text, never run data
        items_note = report["notes"]["items"]  # and they say what twins really feed, the all-items cost included
        assert "per_item_all_items" in items_note and "AC-2" in items_note and " only" not in items_note


def test_missed_true_matches_is_a_count_in_every_cell_and_there_is_no_combined_score(scored):
    report = scored[2]["reports"][scored[1][0]]
    cells = [report["figures"]["overall"], *report["figures"]["by_framing"].values(),
             *report["figures"]["by_family"].values(), *report["figures"]["true_match_by_secondary_family"].values()]
    assert len(cells) == 1 + 3 + 6 + len(report["figures"]["true_match_by_secondary_family"])
    for cell in cells:
        assert type(cell["missed_true_matches"]) is int and type(cell["ambiguous_closed"]) is int
        assert [name for name in cell if "accuracy" in name or "score" in name] == ["citation_accuracy"]


# ---- a report is written once, and says which code wrote it

def test_every_report_names_the_scoring_codes_commit_and_dirty_flag(scored, three_runs, tmp_path):
    out, ids, done = scored
    assert done["written"] == ids
    for run_id in ids:
        assert json.loads(out.joinpath(run_id, "report.json").read_text(encoding="utf-8"))["scored_by"] == CLEAN
    report, = done["sets"].values()
    assert report["scored_by"] == CLEAN and [run["report_scored_by"] for run in report["runs"]] == [CLEAN] * 3
    # and unpatched, it is the real commit of this repository and its real dirty flag
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    real = score.scoring_state(tmp_path)
    assert real == {"commit": commit, "dirty": harness_run.records.git_state(REPO, tmp_path)[1]}
    fresh = score.score_all(unscored(three_runs, tmp_path), WORLD)
    assert {report["scored_by"]["commit"] for report in fresh["reports"].values()} == {commit}


def test_a_run_that_has_a_report_keeps_it_unless_rescoring_is_asked_for(three_runs, tmp_path):
    out, ids = unscored(three_runs, tmp_path), three_runs[1]
    first = score.score_all(out, WORLD)
    assert first["written"] == ids
    paths = [out.joinpath(run_id, "report.json") for run_id in ids]
    marked = json.loads(paths[0].read_text(encoding="utf-8"))
    marked["scored_by"] = {"commit": "an-older-commit", "dirty": False}
    marked["figures"]["overall"]["missed_true_matches"] = -1  # stands for what older scoring code once wrote
    paths[0].write_text(json.dumps(marked), encoding="utf-8")
    before = [path.read_bytes() for path in paths]

    again = score.score_all(out, WORLD)
    assert again["written"] == [] and [path.read_bytes() for path in paths] == before  # nothing rewritten
    assert again["kept"] == ids and again["reports"] == {}  # a kept report is read for scored_by only, never figures
    report, = again["sets"].values()
    assert [run["report_scored_by"]["commit"] for run in report["runs"]][0] == "an-older-commit"
    assert report["scored_by"] == first["reports"][ids[1]]["scored_by"]
    # the run-set report is worked out afresh from the item lines, not from the kept report
    assert report["pooled"]["figures"]["overall"]["missed_true_matches"] == 3 * first["reports"][ids[1]]["figures"]["overall"]["missed_true_matches"]

    out.joinpath(ids[2], "report.json").unlink()
    assert score.score_all(out, WORLD)["written"] == [ids[2]]  # only the run that has none
    assert [path.read_bytes() for path in paths[:2]] == before[:2]

    redone = score.score_all(out, WORLD, rescore=True)
    assert redone["written"] == ids and redone["reports"][ids[0]]["figures"]["overall"]["missed_true_matches"] > 0
    assert json.loads(paths[0].read_text(encoding="utf-8"))["scored_by"] == first["reports"][ids[1]]["scored_by"]


# ---- the hidden-file check, the order of the checks, and the refusals

def world_copy(folder):
    world = folder.joinpath("world")
    shutil.copytree(WORLD, world)
    return world


def test_the_hidden_check_command_passes_on_the_world_and_loads_no_truth(capsys):
    assert main(["check-hidden", str(WORLD)]) == 0
    assert "hidden files match" in capsys.readouterr().out
    seen = python("import json, sys; from harness.__main__ import main; code = main(['check-hidden', sys.argv[1]]); "
                  "print(json.dumps([code, 'worldgen.truth' in sys.modules, 'harness.score' in sys.modules]))", str(WORLD))
    assert seen == [0, False, False]  # exit code 0, and neither the truth nor the scoring code was loaded


@pytest.mark.parametrize("name", ["labels.jsonl", "supporting_evidence.jsonl", "snippet_tags.jsonl", "twin_links.jsonl"])
def test_the_hidden_check_command_fails_on_a_changed_hidden_file(tmp_path, capsys, name):
    world = world_copy(tmp_path)
    with world.joinpath("hidden", name).open("ab") as file:
        file.write(b" ")
    assert main(["check-hidden", str(world)]) == 1
    assert f"refused: hidden/{name} does not match the world manifest" in capsys.readouterr().err


def test_the_hidden_check_does_not_look_at_the_agent_files(tmp_path):
    world = world_copy(tmp_path)
    with world.joinpath("agent", "customers.jsonl").open("ab") as file:
        file.write(b" ")
    assert main(["check-hidden", str(world)]) == 0  # that is the run step's check, not this one


def unscored(three_runs, folder):
    out = folder.joinpath("out")
    shutil.copytree(three_runs[0], out)
    return out


def nothing_written(out):
    return not out.joinpath("sets").exists() and not list(out.rglob("report.json"))


def test_a_changed_items_file_refuses_that_run_only_and_the_others_are_scored(three_runs, tmp_path, capsys):
    out, ids = unscored(three_runs, tmp_path), three_runs[1]
    with out.joinpath(ids[1], "items.jsonl").open("ab") as file:
        file.write(b"\n")
    done = score.score_all(out, WORLD)
    assert list(done["excluded"]) == [ids[1]] and "does not match the hash in its manifest" in done["excluded"][ids[1]]
    assert sorted(done["written"]) == sorted([ids[0], ids[2]]) and not out.joinpath(ids[1], "report.json").exists()
    report, = done["sets"].values()
    left_out = {run["run_id"]: run["left_out_because"] for run in report["runs"]}
    assert left_out[ids[1]] == [f"refused: {done['excluded'][ids[1]]}"] and report["valid_runs"] == 2
    assert main(["score", str(out), str(WORLD)]) == 1 and not out.joinpath(ids[1], "report.json").exists()
    assert f"excluded {ids[1]}: " in capsys.readouterr().err


def test_when_every_run_to_score_is_refused_nothing_is_written(three_runs, tmp_path):
    out, ids = unscored(three_runs, tmp_path), three_runs[1]
    for run_id in ids:
        with out.joinpath(run_id, "items.jsonl").open("ab") as file:
            file.write(b"\n")
    with pytest.raises(score.ScoreRefused, match="does not match the hash in its manifest"):
        score.score_all(out, WORLD)
    assert nothing_written(out)
    assert main(["score", str(out), str(WORLD)]) == 1 and nothing_written(out)


def one_older_run(three_runs, tmp_path):
    """An output folder holding one older run, copied with its index entry: (folder, its run id, its entry)."""
    out, older = tmp_path.joinpath("out"), three_runs[1][0]
    shutil.copytree(three_runs[0].joinpath(older), out.joinpath(older))
    index = json.loads(three_runs[0].joinpath("index.json").read_text(encoding="utf-8"))
    entry, = [run for run in index["runs"] if run["run_id"] == older]
    out.joinpath("index.json").write_text(json.dumps({**index, "runs": [entry]}), encoding="utf-8")
    return out, older, entry


def test_run_and_score_after_a_damaged_older_run_still_reports_the_new_run(three_runs, tmp_path, capsys):
    out, older, entry = one_older_run(three_runs, tmp_path)
    with out.joinpath(older, "items.jsonl").open("ab") as file:  # and then damaged
        file.write(b"\n")
    assert main(["run-and-score", str(write_config(tmp_path)), str(out)]) == 1  # non-zero: a run was refused
    newer, = [run["run_id"] for run in json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
              if run["run_id"] != older]
    report = json.loads(out.joinpath(newer, "report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == newer and report["figures"]["overall"]  # the new run has its report
    assert not out.joinpath(older, "report.json").exists()
    set_report = json.loads(out.joinpath("sets", entry["run_set"] + ".json").read_text(encoding="utf-8"))
    left_out = {run["run_id"]: run["left_out_because"] for run in set_report["runs"]}
    assert left_out[older][0].startswith("refused: ") and "does not match the hash" in left_out[older][0]
    assert f"excluded {older}: " in capsys.readouterr().err


def test_a_changed_hidden_file_is_refused_and_nothing_is_written(three_runs, tmp_path):
    out, world = unscored(three_runs, tmp_path), world_copy(tmp_path)
    with world.joinpath("hidden", "labels.jsonl").open("ab") as file:
        file.write(b" ")
    with pytest.raises(harness_run.WorldMismatch, match="hidden/labels.jsonl"):
        score.score_all(out, world)
    assert nothing_written(out)


def test_another_world_is_refused_and_nothing_is_written(three_runs, tmp_path):
    out, world = unscored(three_runs, tmp_path), world_copy(tmp_path)
    listed = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    listed["world_hash"] = "0" * 64
    world.joinpath("MANIFEST.json").write_text(json.dumps(listed), encoding="utf-8")
    with pytest.raises(score.ScoreRefused, match="another world"):
        score.score_all(out, world)
    assert nothing_written(out)


def test_an_aborted_run_is_never_scored(tmp_path, monkeypatch):
    def exploding(items, model, settings, item_id):
        raise RuntimeError("boom")

    monkeypatch.setitem(harness_run.AGENTS, "exploding", exploding)
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(write_config(tmp_path, agent="exploding"), out)
    done = score.score_all(out, WORLD)
    assert done["reports"] == {} and not list(out.rglob("report.json"))
    report, = done["sets"].values()
    assert report["runs"] == [{"run_id": manifest["run_id"], "state": "aborted", "valid": False,
                               "left_out_because": ["aborted"], "report_scored_by": None}]
    assert report["valid_runs"] == 0 and report["pooled"] is None and report["eligible_as_baseline"] is False


def test_run_and_score_on_a_run_that_aborts_scores_nothing_and_writes_no_report(tmp_path, monkeypatch, capsys):
    def exploding(items, model, settings, item_id):
        raise RuntimeError("boom")

    monkeypatch.setitem(harness_run.AGENTS, "exploding", exploding)
    out = tmp_path.joinpath("out")
    assert main(["run-and-score", str(write_config(tmp_path, agent="exploding")), str(out)]) == 1
    entry, = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == "aborted"
    assert not list(out.rglob("report.json")) and not out.joinpath("sets").exists()  # the score step never ran
    assert capsys.readouterr().out == f"{entry['run_id']}: aborted\n"  # and printed nothing about reports



def _without_outputs(manifest_path, items_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["outputs"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


DAMAGE = {  # name: (what is done to the older run, what the reason must say)
    "missing outputs": (_without_outputs, "its manifest lacks outputs"),
    "invalid JSON manifest": (lambda manifest, items: manifest.write_text("{not json", encoding="utf-8"), "cannot read"),
    "missing items file": (lambda manifest, items: items.unlink(), "cannot read items.jsonl"),
    "empty manifest": (lambda manifest, items: manifest.write_text("", encoding="utf-8"), "cannot read"),
    "manifest of the wrong type": (lambda manifest, items: manifest.write_text("[1, 2]", encoding="utf-8"),
                                   "its manifest is a list, not an object"),
}


@pytest.mark.parametrize("damage", list(DAMAGE))
def test_an_older_run_that_cannot_be_loaded_is_quarantined_and_the_new_run_still_gets_its_report(
        three_runs, tmp_path, capsys, damage):
    out, older, entry = one_older_run(three_runs, tmp_path)
    harm, reason = DAMAGE[damage]
    harm(out.joinpath(older, "manifest.json"), out.joinpath(older, "items.jsonl"))
    assert main(["run-and-score", str(write_config(tmp_path)), str(out)]) == 1  # non-zero: a run was refused
    newer, = [run["run_id"] for run in json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
              if run["run_id"] != older]
    assert json.loads(out.joinpath(newer, "report.json").read_text(encoding="utf-8"))["run_id"] == newer
    assert not out.joinpath(older, "report.json").exists()
    set_report = json.loads(out.joinpath("sets", entry["run_set"] + ".json").read_text(encoding="utf-8"))
    left_out = {run["run_id"]: run["left_out_because"] for run in set_report["runs"]}
    assert left_out[older][0].startswith(f"refused: {older}: ") and reason in left_out[older][0], left_out[older]
    assert f"excluded {older}: " in capsys.readouterr().err


def _rehash(run_dir):
    """Write the hash of the items file into the manifest again, so that a changed item passes the hash check."""
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    manifest["outputs"]["sha256"] = harness_run.records.sha256(run_dir.joinpath("items.jsonl").read_bytes())
    run_dir.joinpath("manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _wrong_type_price(run_dir):
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    manifest["price_table"]["table"]["models"]["fake-1"]["input"] = 5  # a number, where a decimal string belongs
    run_dir.joinpath("manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _integer_cited_ids(run_dir):
    lines = run_dir.joinpath("items.jsonl").read_text(encoding="utf-8").split("\n")
    number = next(number for number, line in enumerate(lines) if line and not json.loads(line)["result"]["system_failure"])
    item = json.loads(lines[number])
    item["result"]["cited_ids"] = 7  # an integer, where a list of evidence IDs belongs
    lines[number] = json.dumps(item, sort_keys=True)
    run_dir.joinpath("items.jsonl").write_text("\n".join(lines), encoding="utf-8")
    _rehash(run_dir)


LATE_DAMAGE = {  # damage the round-4 review found: (what is done to the older run, what the reason says)
    "wrong-type price": (_wrong_type_price, "its price table fails the run-step check"),
    "integer cited_ids": (_integer_cited_ids, ".result.cited_ids is not a list"),
    "invalid report.json": (lambda run_dir: run_dir.joinpath("report.json").write_text("{bad", encoding="utf-8"),
                            "cannot be scored: JSONDecodeError"),
    "deleted manifest": (lambda run_dir: run_dir.joinpath("manifest.json").unlink(),
                         "the index lists it as completed, but its manifest.json is missing"),
}


@pytest.mark.parametrize("damage", list(LATE_DAMAGE))
def test_late_damage_to_an_older_run_quarantines_it_and_the_new_report_is_still_written(three_runs, tmp_path, capsys, damage):
    out, older, entry = one_older_run(three_runs, tmp_path)
    harm, reason = LATE_DAMAGE[damage]
    harm(out.joinpath(older))
    assert main(["run-and-score", str(write_config(tmp_path)), str(out)]) == 1  # non-zero: a run was refused
    newer, = [run["run_id"] for run in json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
              if run["run_id"] != older]
    assert json.loads(out.joinpath(newer, "report.json").read_text(encoding="utf-8"))["run_id"] == newer
    set_report = json.loads(out.joinpath("sets", entry["run_set"] + ".json").read_text(encoding="utf-8"))
    left_out = {run["run_id"]: run["left_out_because"] for run in set_report["runs"]}
    assert left_out[older][0].startswith(f"refused: {older}: ") and reason in left_out[older][0], left_out[older]
    assert [run["run_id"] for run in set_report["runs"]][0] == newer  # the new run was scored first
    assert f"excluded {older}: " in capsys.readouterr().err


def test_a_kept_report_without_scored_by_makes_the_set_need_rescoring_and_never_eligible(three_runs, tmp_path, capsys):
    out, older, entry = one_older_run(three_runs, tmp_path)
    out.joinpath(older, "report.json").write_text(json.dumps({"figures": "never read"}), encoding="utf-8")
    assert main(["run-and-score", str(write_config(tmp_path)), str(out)]) == 0  # not refused: scored afresh
    set_report = json.loads(out.joinpath("sets", entry["run_set"] + ".json").read_text(encoding="utf-8"))
    by = {run["run_id"]: run["report_scored_by"] for run in set_report["runs"]}
    assert by[older] is None and set_report["rescore_needed"] is True and set_report["eligible_as_baseline"] is False
    assert json.loads(out.joinpath(older, "report.json").read_text(encoding="utf-8")) == {"figures": "never read"}  # kept


# ---- round 5: the order of the work, and validate_run

def test_run_and_score_writes_the_new_report_before_it_loads_any_older_run(three_runs, tmp_path, monkeypatch):
    out, older, entry = one_older_run(three_runs, tmp_path)
    events, real_load, real_write = [], score._load_run, score.records.write_json

    def load(out_dir, run, world_hash):
        events.append(("load", run["run_id"]))
        return real_load(out_dir, run, world_hash)

    def write(path, value):
        events.append(("write", Path(path).parent.name if Path(path).name == "report.json" else Path(path).name))
        return real_write(path, value)

    monkeypatch.setattr(score, "_load_run", load)
    monkeypatch.setattr(score.records, "write_json", write)
    assert main(["run-and-score", str(write_config(tmp_path)), str(out)]) == 0
    newer, = {run_id for kind, run_id in events if kind == "load"} - {older}
    assert events.index(("write", newer)) < events.index(("load", older)), events  # the real I/O order


def micro_run():
    """A small valid run in memory, two items, one of them a twin, that passes the whole shared schema:
    (index entry, manifest, items)."""
    prices = json.loads(FIXTURES.joinpath("prices.json").read_text(encoding="utf-8"))
    times = json.loads(FIXTURES.joinpath("modelled_time.json").read_text(encoding="utf-8"))
    hashes = {"price_table": harness_run.records.content_hash(prices), "modelled_time": harness_run.records.content_hash(times)}
    inputs = {"agent": "inprocess", "commit": "c" * 40, "world_hash": "e" * 64, "prompt_hash": "a" * 64,
              "model_config": "b" * 64, "workers": 1, "pacer_per_minute": None, "infra_invalid_threshold": "0.05", **hashes}
    run_set = harness_run.records.content_hash(inputs)

    def row(alert_id, twin):
        return {"item_id": f"{alert_id}/1", "alert_id": alert_id, "framing": 1, "twin": twin, "sent_ids": ["E1"],
                "wall_s": 0.5, "queue_s": 0.0, "attempts": [{"error": None, "input_tokens": 3, "output_tokens": 2, "model_id": "fake-1"}],
                "result": {"recommendation": "CLOSE", "reason": "r", "cited_ids": ["E1"], "system_failure": False,
                           "failure_kind": None, "citation_invalid": False,
                           "log": {"kind": "result", "error_name": None, "attempts": 1,
                                   "attempt_log": [{"error_name": None, "latency_s": 0.1}], "latency_s": 0.1,
                                   "model_id": "fake-1", "correlation_id": f"{alert_id}/1"}}}

    calls = {"attempts": 2, "without_token_counts": 0, "input_tokens": 6, "output_tokens": 4}
    cost = {"known_cost": {"numerator": 7, "denominator": 500000, "not_applicable": False, "decimal": "0.000014",
                           "rounded": False},
            "currency": "USD", "attempts": 2, "attempts_without_token_counts": 0, "attempts_without_price": 0,
            "at_least": False, "statement": "0.000014 USD"}
    started = "2026-10-15T00:00:00+00:00"
    manifest = {
        "run_id": "R1", "run_set": run_set, "run_set_inputs": inputs, "state": "completed", "aborted": None,
        "rerun_cause": None, "agent": "inprocess",
        "world": {"world_hash": "e" * 64, "generator_version": "1", "rubric_version": "1.2"},
        "model": {"used": True, "provider": "fake", "requested": "fake-1", "reported": {"fake-1": 2}},
        "prompt": {"text": "prompt", "sha256": "a" * 64}, "decoding": {"temperature": 0, "max_tokens": 512},
        "retry_policy": {"retries": 2, "timeout_s": 30, "retried_errors": ["ModelTimeout"], "backoff": None},
        "review_policies": ["STRICT_FOUR_EYES", "none"],
        "modelled_time": {"sha256": hashes["modelled_time"], "parameters": times},
        "price_table": {"sha256": hashes["price_table"], "table": prices},
        "outputs": {"items_file": "items.jsonl", "sha256": "0" * 64},
        "git": {"commit": "c" * 40, "dirty": False}, "config_sha256": "d" * 64, "framing_code_sha256": "f" * 64,
        "python_version": "3.12.3", "workers": 1, "pacer_per_minute": None,
        "infra_invalid": {"threshold": "0.05", "transient_items": 0, "transient_share": "0", "marked": False},
        "started_at": started, "ended_at": "2026-10-15T00:00:01+00:00", "timing": {"duration_s": 1.0, "queue_s": 0.0},
        "items": {"main": 1, "twin": 1, "total": 2}, "calls": calls, "cost": cost}
    entry = {"run_id": "R1", "run_set": run_set, "state": "completed", "dirty": False, "infra_invalid": False,
             "cause": None, "rerun_cause": None, "calls": copy.deepcopy(calls), "cost": copy.deepcopy(cost),
             "started_at": started}
    return entry, manifest, [row("A1", False), row("T1", True)]


def _set(path, value):
    """A change to one place in (entry, manifest, items), given as a path of keys and indexes."""
    def change(run):
        here = run
        for key in path[:-1]:
            here = here[key]
        here[path[-1]] = value
    return change


VALIDATE = {  # name: (a change to a valid micro run, what the refusal must say)
    "manifest not an object": (lambda run: run.__setitem__(1, []), "its manifest is a list, not an object"),
    "index and manifest disagree on run_id": (_set((0, "run_id"), "R2"), "disagree on run_id"),
    "index and manifest disagree on run_set": (_set((0, "run_set"), "0" * 64), "disagree on run_set"),
    "index and manifest disagree on state": (_set((0, "state"), "aborted"), "disagree on state"),
    "run-set ID does not match its inputs": (_set((1, "run_set_inputs", "agent"), "always_close"), "does not match its run-set inputs"),
    "dirty flag not a boolean": (_set((1, "git", "dirty"), 0), "its manifest.git.dirty is not a boolean"),
    "infrastructure mark not a boolean": (_set((1, "infra_invalid", "marked"), 0), "its manifest.infra_invalid.marked is not a boolean"),
    "price table fails its check": (_set((1, "price_table", "table", "kind"), "guessed"), "price table fails the run-step check"),
    "modelled-time file fails its check": (_set((1, "modelled_time", "parameters", "kind"), "guessed"), "modelled-time file fails the run-step check"),
    "price table changed after the run": (_set((1, "price_table", "table", "models", "fake-1", "input"), "9.00"), "price table does not match its recorded hash"),
    "item counts not whole numbers": (_set((1, "items", "total"), 2.0), "its manifest.items.total is not a whole number of 0 or more"),
    "row missing a field": (lambda run: run[2][0].pop("sent_ids"), "item row 1 lacks sent_ids"),
    "row field of the wrong type": (_set((2, 0, "twin"), "false"), "item row 1.twin is not a boolean"),
    "result field of the wrong type": (_set((2, 0, "result", "system_failure"), 0), "item row 1.result.system_failure is not a boolean"),
    "framing out of range": (_set((2, 0, "framing"), 4), "item row 1.framing is not one of the framings 1, 2 and 3"),
    "item_id not made of alert_id and framing": (_set((2, 0, "item_id"), "A1/2"), "item_id, alert_id and framing do not agree"),
    "recommendation unknown": (_set((2, 0, "result", "recommendation"), "MAYBE"), "item row 1.result.recommendation is not CLOSE or ESCALATE"),
    "cited ID not text": (_set((2, 0, "result", "cited_ids"), [1]), "item row 1.result.cited_ids[0] is not text"),
    "latency not a number": (_set((2, 0, "result", "log", "latency_s"), "fast"), "item row 1.result.log.latency_s is not a finite number"),
    "attempt of the wrong type": (_set((2, 0, "attempts", 0, "input_tokens"), "3"), "item row 1.attempts[0].input_tokens is not a whole number"),
    "count of items differs": (lambda run: run[2].append(copy.deepcopy(run[2][0]) | {"item_id": "A9/1", "alert_id": "A9"}),
                               "it has 3 items, 2 main and 1 twin, but its manifest says 2, 1 and 1"),
    "an item ID twice": (lambda run: (run[2].append(copy.deepcopy(run[2][0])), run[1]["items"].update(main=2, total=3)),
                         "an item ID appears more than once"),
}


def test_validate_run_refuses_each_kind_of_bad_run_and_accepts_a_good_one():
    score.validate_run(*micro_run())  # the untouched micro run passes
    for name, (change, reason) in VALIDATE.items():
        run = list(micro_run())
        change(run)
        with pytest.raises(score.ScoreRefused, match=re.escape(reason)):
            score.validate_run(*run)


ROUND_6 = {  # the rules added in review round 6: (a change to a valid micro run, what the refusal must say)
    "negative input tokens": (_set((2, 0, "attempts", 0, "input_tokens"), -3), "item row 1.attempts[0].input_tokens is not a whole number of 0 or more"),
    "negative output tokens": (_set((2, 0, "attempts", 0, "output_tokens"), -1), "item row 1.attempts[0].output_tokens is not a whole number of 0 or more"),
    "negative wall_s": (_set((2, 0, "wall_s"), -0.5), "item row 1.wall_s is not a finite number of 0 or more"),
    "NaN wall_s": (_set((2, 0, "wall_s"), float("nan")), "item row 1.wall_s is not a finite number of 0 or more"),
    "infinite wall_s": (_set((2, 0, "wall_s"), float("inf")), "item row 1.wall_s is not a finite number of 0 or more"),
    "negative queue_s": (_set((2, 0, "queue_s"), -0.1), "item row 1.queue_s is not a finite number of 0 or more"),
    "NaN queue_s": (_set((2, 0, "queue_s"), float("nan")), "item row 1.queue_s is not a finite number of 0 or more"),
    "infinite queue_s": (_set((2, 0, "queue_s"), float("inf")), "item row 1.queue_s is not a finite number of 0 or more"),
    "None latency_s": (_set((2, 0, "result", "log", "latency_s"), None), "item row 1.result.log.latency_s is not a finite number of 0 or more"),
    "wall_s below the agent latency": (_set((2, 0, "wall_s"), 0.05), "wall-clock time is shorter than the agent's own latency"),
    "index and manifest disagree on dirty": (_set((0, "dirty"), True), "disagree on dirty"),
    "index and manifest disagree on the mark": (_set((0, "infra_invalid"), True), "disagree on infra_invalid"),
    "index and manifest disagree on calls": (_set((0, "calls", "attempts"), 3), "disagree on calls"),
    "index and manifest disagree on cost": (_set((0, "cost", "statement"), "0 USD"), "disagree on cost"),
    "index and manifest disagree on the re-run cause": (_set((0, "rerun_cause"), "again"), "disagree on rerun_cause"),
    "index and manifest disagree on the start time": (_set((0, "started_at"), "2026-10-16T00:00:00+00:00"), "disagree on started_at"),
    "index and manifest disagree on the cause": (_set((0, "cause"), "RuntimeError: boom"), "disagree on cause"),
    "a mark the rows do not give": (lambda run: (run[0].update(infra_invalid=True), run[1]["infra_invalid"].update(marked=True)),
                                    "mark does not follow from its transient failures, items and threshold"),
    "a transient count the rows do not give": (_set((1, "infra_invalid", "transient_items"), 1),
                                               "its item rows hold 0 transient failures, but its manifest says 1"),
    "a threshold not among the run-set inputs": (_set((1, "infra_invalid", "threshold"), "0.5"),
                                                 "threshold is not the one among its run-set inputs"),
}


def test_validate_run_refuses_each_kind_of_bad_run_added_in_round_6():
    score.validate_run(*micro_run())  # the untouched micro run passes
    for name, (change, reason) in ROUND_6.items():  # each case is checked by the shared schema
        run = list(micro_run())
        change(run)
        with pytest.raises(score.ScoreRefused, match=re.escape(reason)):
            score.validate_run(*run)


def test_a_refused_fourth_completed_run_makes_the_set_ineligible_and_is_named(monkeypatch):
    monkeypatch.setattr(score, "set_figures", lambda *arguments, **options: {"pooled": {}, "spread": {}})
    monkeypatch.setattr(score, "acceptance", lambda *arguments, **options: {})
    clean = {"commit": "c" * 40, "dirty": False}
    good = [{"run_id": name, "state": "completed", "left_out_because": [], "report_scored_by": clean} for name in "abc"]
    group = {"runs": good, "valid": dict.fromkeys("abc", []), "tables": ({"kind": "fixture"}, {"kind": "fixture"}),
             "aborted": [], "table_hashes": {("p1", "t1")}}
    three = score._set_report("S", group, {"sets": {}}, clean, dict.fromkeys("abc", {}), {})
    assert three["eligible_as_baseline"] is True and three["refused_runs"] == []
    group["runs"] = good + [{"run_id": "d", "state": "completed", "report_scored_by": None,
                             "left_out_because": ["refused: d: its dirty flag is not a boolean"]}]
    four = score._set_report("S", group, {"sets": {}}, clean, dict.fromkeys("abc", {}), {})
    assert four["eligible_as_baseline"] is False  # fail closed: three good runs are not enough beside a refused one
    assert four["refused_runs"] == [{"run_id": "d", "reason": "d: its dirty flag is not a boolean"}]


class _Read(dict):
    """A dictionary that notes every field read from it, by its path."""
    def __init__(self, value, path, seen):
        super().__init__(value)
        self._path, self._seen = path, seen

    def __getitem__(self, key):
        self._seen.add(f"{self._path}.{key}")
        return _noting(super().__getitem__(key), f"{self._path}.{key}", self._seen)

    def get(self, key, default=None):
        if key not in self:
            return default
        return self[key]


def _noting(value, path, seen):
    if isinstance(value, dict) and not isinstance(value, _Read):
        return _Read(value, path, seen)
    if isinstance(value, list):
        return [_noting(item, path + "[]", seen) for item in value]
    return value


def test_the_score_step_reads_no_field_of_a_run_that_the_schema_does_not_list(three_runs, tmp_path, monkeypatch):
    out, older, entry = one_older_run(three_runs, tmp_path)
    seen, real_json, real_index = set(), score._json, score.records.read_index
    monkeypatch.setattr(score, "_json", lambda path, error=ValueError: _noting(real_json(path, error), "manifest", seen)
                        if Path(path).name == "manifest.json" else real_json(path, error))
    monkeypatch.setattr(score, "json", types.SimpleNamespace(loads=lambda text: _noting(json.loads(text), "item", seen),
                                                             dumps=json.dumps))
    monkeypatch.setattr(score.records, "read_index", lambda out: {**real_index(out), "runs": [
        _noting(run, "index", seen) for run in real_index(out)["runs"]]})
    score.score_all(out, WORLD)
    listed = {f"manifest.{path}" for path in schema.keys(schema.MANIFEST)}
    listed |= {f"item.{path}" for path in schema.keys(schema.ITEM_ROW)}
    listed |= {f"item.attempts[].{path}" for path in schema.keys(schema.ATTEMPT)}
    listed |= {f"index.{path}" for path in schema.keys(schema.INDEX_ENTRY)}
    checked_whole = ("manifest.price_table.table.", "manifest.modelled_time.parameters.")  # by the run-step checks
    unlisted = sorted(path for path in seen if path not in listed and not path.startswith(checked_whole))
    assert not unlisted, unlisted  # a field the score step reads must be in the schema
    assert {"item.result.cited_ids", "item.attempts[].input_tokens", "manifest.git.dirty", "index.dirty"} <= seen


def micro_aborted():
    """The micro run as an aborted run: (index entry, manifest), both as the run step writes them."""
    entry, manifest, _ = micro_run()
    manifest.update(state="aborted", aborted={"item_id": "A1/1", "error_type": "RuntimeError", "message": "boom"},
                    outputs=None, infra_invalid={"threshold": "0.05", "transient_items": 0, "transient_share": None,
                                                 "marked": None})
    entry.update(state="aborted", infra_invalid=None, cause="RuntimeError: boom")
    return entry, manifest


def _both(path, value):
    """The same change to the index entry and the manifest, so that they still agree."""
    def change(run):
        for side in (0, 1):
            _set((side, *path), value)(run)
    return change


ROUND_7 = {  # review round 7, findings B1 to B4: (what is checked, a change, what the refusal must say)
    # B2 first: with the shared schema checking nothing this case raises nothing (see "the shared schema checks nothing")
    "B2 a failure kind no agent writes": ("run", _set((2, 0, "result", "failure_kind"), "made_up"),
                                          "item row 1.result.failure_kind is not null or one of the failure kinds"),
    "B1 an index state that is no state": ("index", lambda entry: entry.update(state="bogus"), "its index entry.state is not one of"),
    "B1 an index run set that is no run-set ID": ("index", lambda entry: entry.update(run_set="not-a-hash"),
                                                  "its index entry.run_set is not 64 lowercase hex digits"),
    "B1 an index entry without a field": ("index", lambda entry: entry.pop("dirty"), "its index entry lacks dirty"),
    "B1 an index entry with a key no one writes": ("index", lambda entry: entry.update(extra=1),
                                                   "a key the schema does not name: extra"),
    "B1 an index run set its manifest does not have": ("run", _set((0, "run_set"), "a" * 64), "disagree on run_set"),
    "B3 calls.attempts -1 in both": ("run", _both(("calls", "attempts"), -1), "its manifest.calls.attempts is not a whole number"),
    "B3 a cost statement that is no text": ("run", _both(("cost", "statement"), 5), "its manifest.cost.statement is not non-empty text"),
    "B3 a known-cost denominator of 0": ("run", _both(("cost", "known_cost", "denominator"), 0),
                                         "its manifest.cost.known_cost.denominator is not a whole number of 1 or more"),
    "B3 a git commit that is no commit": ("run", _set((1, "git", "commit"), 7), "its manifest.git.commit is not"),
    "B3 a transient share that is no decimal": ("run", _set((1, "infra_invalid", "transient_share"), "a lot"),
                                                "its manifest.infra_invalid.transient_share is not a decimal text"),
    "B3 a run duration below 0": ("run", _set((1, "timing", "duration_s"), -1), "its manifest.timing.duration_s is not a finite number"),
    "B3 an end time that is no time": ("run", _set((1, "ended_at"), "yesterday"), "its manifest.ended_at is not an ISO date"),
    "B3 a model count below 0": ("run", _set((1, "model", "reported", "fake-1"), -1), "its manifest.model.reported.fake-1 is not"),
    "B3 a decoding block of the wrong type": ("run", _set((1, "decoding"), "hot"), "its manifest.decoding is not an object"),
    "B3 a retry policy without retries": ("run", lambda run: run[1]["retry_policy"].pop("retries"), "its manifest.retry_policy lacks retries"),
    "B3 a review policy no one names": ("run", _set((1, "review_policies"), ["QA"]), "its manifest.review_policies[0] is not"),
    "B3 a config hash that is no hash": ("run", _set((1, "config_sha256"), "x"), "its manifest.config_sha256 is not 64"),
    "B3 workers 0 in both": ("run", lambda run: (run[1].update(workers=0), run[1]["run_set_inputs"].update(workers=0),
                                                 run[0].update(run_set=harness_run.records.content_hash(run[1]["run_set_inputs"])),
                                                 run[1].update(run_set=run[0]["run_set"])),
                             "its manifest.run_set_inputs.workers is not a whole number from 1 to 64"),
    "B3 a pacer setting of 0 in both": ("run", lambda run: (run[1].update(pacer_per_minute=0), run[1]["run_set_inputs"].update(pacer_per_minute=0),
                                                            run[0].update(run_set=harness_run.records.content_hash(run[1]["run_set_inputs"])),
                                                            run[1].update(run_set=run[0]["run_set"])),
                                        "its manifest.run_set_inputs.pacer_per_minute is not"),
    "B3 a prompt hash that is no hash": ("run", _set((1, "prompt", "sha256"), "x"), "its manifest.prompt.sha256 is not 64"),
    "B4 an abort record that is a list": ("aborted", _set((1, "aborted"), ["boom"]), "its manifest.aborted is not an object"),
    "B4 aborted calls below 0 in both": ("aborted", _both(("calls", "input_tokens"), -5), "its manifest.calls.input_tokens is not"),
    "B4 an aborted run with outputs": ("aborted", _set((1, "outputs"), {"items_file": "items.jsonl", "sha256": "0" * 64}),
                                       "its manifest.outputs is not null"),
    "B4 an aborted run that has a mark": ("aborted", _set((1, "infra_invalid", "marked"), False),
                                          "its manifest.infra_invalid.marked is not null"),
}


def test_each_round_7_finding_is_refused_on_a_small_run_in_memory():
    score.validate_run(*micro_run())  # both untouched micro runs pass
    score.validate_run(*micro_aborted(), None)
    assert score.check_index({"runs": [micro_run()[0]], "sets": {}}) == ([micro_run()[0]], [])
    for name, (kind, change, reason) in ROUND_7.items():
        if kind == "index":
            entry = micro_run()[0]
            change(entry)
            good, problems = score.check_index({"runs": [entry], "sets": {}})
            assert good == [] and len(problems) == 1 and reason in problems[0][1], (name, problems)
            continue
        run = list(micro_run()) if kind == "run" else [*micro_aborted(), None]
        change(run)
        with pytest.raises(score.ScoreRefused, match=re.escape(reason)):
            score.validate_run(*run)


def test_while_any_index_entry_or_run_cannot_be_placed_in_a_set_no_set_is_eligible(monkeypatch):
    monkeypatch.setattr(score, "set_figures", lambda *arguments, **options: {"pooled": {}, "spread": {}})
    monkeypatch.setattr(score, "acceptance", lambda *arguments, **options: {})
    clean = {"commit": "c" * 40, "dirty": False}
    good = [{"run_id": name, "state": "completed", "left_out_because": [], "report_scored_by": clean} for name in "abc"]
    group = {"runs": good, "valid": dict.fromkeys("abc", []), "tables": ({"kind": "fixture"}, {"kind": "fixture"}),
             "aborted": [], "table_hashes": {("p1", "t1")}}
    fresh = dict.fromkeys("abc", {})
    assert score._set_report("S", group, {"sets": {}}, clean, fresh, {})["eligible_as_baseline"] is True
    reason = "d: its index entry.state is not one of ['aborted', 'completed', 'started']: 'bogus'"
    report = score._set_report("S", group, {"sets": {}}, clean, fresh, {}, [reason])
    assert report["eligible_as_baseline"] is False and report["unassigned"] == [reason]  # fail closed, and why


def test_a_bogus_index_entry_makes_every_set_ineligible_in_a_real_score_step(three_runs, tmp_path, clean_scoring):
    out, ids = unscored(three_runs, tmp_path), three_runs[1]
    index = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))
    stray = dict(index["runs"][0], run_id="stray", state="bogus")  # one hand-altered entry, no files at all
    out.joinpath("index.json").write_text(json.dumps({**index, "runs": index["runs"] + [stray]}), encoding="utf-8")
    done = score.score_all(out, WORLD)
    report, = done["sets"].values()
    assert report["valid_runs"] == 3 and report["refused_runs"] == []  # the three good runs are scored as before
    assert report["eligible_as_baseline"] is False  # but the stray entry could belong to any set: fail closed
    assert report["unassigned"] == [done["excluded"]["stray"]] and "is not one of" in report["unassigned"][0]


@pytest.fixture(scope="module")
def one_real_run(three_runs):
    """The index entry, manifest and item lines of one real run, as the score step loads them, read once."""
    out, run_id = three_runs[0], three_runs[1][0]
    entry, = [run for run in json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"] if run["run_id"] == run_id]
    manifest = json.loads(out.joinpath(run_id, "manifest.json").read_text(encoding="utf-8"))
    items = [json.loads(line) for line in out.joinpath(run_id, "items.jsonl").read_text(encoding="utf-8").split("\n") if line]
    return entry, manifest, items


def _twin_false(run):
    run[2][0]["twin"] = "false"  # what a rehashed row can carry: text where a boolean belongs


def _rehashed_row(run):
    run[2][0]["result"]["recommendation"] = "ESCALATE" if run[2][0]["result"]["recommendation"] == "CLOSE" else "CLOSE"
    run[2][0]["twin"] = not run[2][0]["twin"]  # moved between main and twin: the counts no longer match


CODEX_PROBES = {  # the six probes of review round 5, on a real run, as the review made them
    "index against manifest": (_set((0, "run_set"), "1" * 64), "disagree on run_set"),
    "numeric 0 for dirty and marked": (lambda run: (run[1]["git"].update(dirty=0), run[1]["infra_invalid"].update(marked=0)),
                                       "its manifest.git.dirty is not a boolean"),
    "invalid kind in both tables": (lambda run: (run[1]["price_table"]["table"].update(kind="other"),
                                                 run[1]["modelled_time"]["parameters"].update(kind="other")),
                                    "price table fails the run-step check"),
    "changed older price": (_set((1, "price_table", "table", "models", "fake-1", "output"), "20.00"),
                            "price table does not match its recorded hash"),
    "twin \"false\"": (_twin_false, "item row 1.twin is not a boolean"),
    "rehashed item row": (_rehashed_row, "but its manifest says 1845, 1800 and 45"),
}


@pytest.mark.parametrize("probe", list(CODEX_PROBES))
def test_each_codex_probe_of_round_5_is_refused(one_real_run, probe):
    run = copy.deepcopy(list(one_real_run))
    score.validate_run(*run)  # the real run passes untouched
    change, reason = CODEX_PROBES[probe]
    change(run)
    with pytest.raises(score.ScoreRefused, match=re.escape(reason)):
        score.validate_run(*run)


def test_a_set_whose_runs_do_not_all_have_the_same_tables_is_never_eligible(monkeypatch):
    monkeypatch.setattr(score, "set_figures", lambda *arguments, **options: {"pooled": {}, "spread": {}})
    monkeypatch.setattr(score, "acceptance", lambda *arguments, **options: {})
    clean = {"commit": "c" * 40, "dirty": False}
    group = {"runs": [{"run_id": name, "report_scored_by": clean} for name in "abc"], "valid": dict.fromkeys("abc", []),
             "tables": ({"kind": "fixture"}, {"kind": "fixture"}), "aborted": [], "table_hashes": {("p1", "t1")}}
    fresh = dict.fromkeys("abc", {})
    same = score._set_report("S", group, {"sets": {}}, clean, fresh, {})
    assert same["identical_tables"] is True and same["eligible_as_baseline"] is True
    group["table_hashes"].add(("p2", "t1"))  # one run priced with another table
    differ = score._set_report("S", group, {"sets": {}}, clean, fresh, {})
    assert differ["identical_tables"] is False and differ["eligible_as_baseline"] is False


def test_an_error_computing_the_new_runs_figures_stops_loudly_and_writes_nothing(tmp_path, monkeypatch):
    def broken(*arguments, **options):
        raise ZeroDivisionError("a bug in the figures")

    monkeypatch.setattr(score, "figures", broken)
    out = tmp_path.joinpath("out")
    with pytest.raises(ZeroDivisionError, match="a bug in the figures"):  # a bug in the new run is never hidden
        main(["run-and-score", str(write_config(tmp_path)), str(out)])
    assert nothing_written(out)


def test_the_score_command_refuses_and_writes_nothing_when_every_run_fails_while_scored(three_runs, tmp_path, monkeypatch):
    out = unscored(three_runs, tmp_path)

    def broken(*arguments, **options):
        raise ZeroDivisionError("a bug in the figures")

    monkeypatch.setattr(score, "figures", broken)
    with pytest.raises(score.ScoreRefused, match="cannot be scored: ZeroDivisionError: a bug in the figures"):
        score.score_all(out, WORLD)  # no new run: every run is isolated, and when all are refused, nothing is written
    assert nothing_written(out)


ORDER_PROBE = """
import json, sys
from pathlib import Path
out, opens, state = Path(sys.argv[2]) / "out", [], {"first": None}


def watch(event, arguments):  # every open under a hidden/ folder; at the first, what the outputs were then
    if event == "open" and "/hidden/" in str(arguments[0]):
        if state["first"] is None:
            files = sorted(path.name for path in out.rglob("*") if path.is_file())
            state["first"] = [files, "worldgen.truth" in sys.modules]
            state["items_read_before"] = state.get("items_read", 0)
        opens.append(str(arguments[0]))
    if event == "open" and str(arguments[0]).endswith("/items.jsonl") and "r" in str(arguments[1] or "r"):
        state["items_read"] = state.get("items_read", 0) + 1  # the score step reads the items file to hash it


sys.addaudithook(watch)
sys.path.insert(0, sys.argv[1])
import pytest, fake_model, conftest
from harness import run, score
with pytest.MonkeyPatch.context() as patch:
    fake_model.register(patch)
    run.run(conftest.write_config(sys.argv[2]), out)
    after_run = len(opens)
    patch.setattr(score, "scoring_state", lambda out: dict(conftest.CLEAN))
    if sys.argv[4:] == ["control"]:  # the positive control: the truth module loaded before the score step
        import worldgen.truth
    score.score_all(out, sys.argv[3])
print(json.dumps({"after_run": after_run, "first": state["first"], "opens": len(opens) - after_run,
                  "items_read_before": state.get("items_read_before")}))
"""


def test_the_truth_is_read_only_after_the_outputs_exist_and_were_checked(tmp_path):
    seen = python(ORDER_PROBE, str(Path(__file__).resolve().parent), str(tmp_path), str(WORLD))
    assert seen["after_run"] == 0  # the whole run step opened nothing under hidden/
    files, truth_loaded = seen["first"]
    assert files == ["audit.jsonl", "checkpoint.json", "index.json", "items.jsonl", "manifest.json"]  # at the first open
    assert truth_loaded is False  # and that first open was the hash check, before the truth module was loaded
    assert seen["opens"] == 7  # four files hashed, then the three that worldgen.truth.load_truth reads
    assert seen["items_read_before"] >= 1  # the items file was read, and so hashed, before the first hidden open


def test_positive_control_the_order_probe_sees_the_truth_loaded_too_early(tmp_path):
    seen = python(ORDER_PROBE, str(Path(__file__).resolve().parent), str(tmp_path), str(WORLD), "control")
    files, truth_loaded = seen["first"]
    assert truth_loaded is True  # loaded on purpose before the first hidden open: the probe must say so
