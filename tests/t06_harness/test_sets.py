"""T06 stage 2: run sets. The pooled headline and the spread over valid runs only, which runs are left out,
when a set can be a baseline, and superseding as an explicit human action (DEC-T06-SPREAD, DEC-T06-FAULTS,
DEC-T06-INFRA-INVALID, DEC-T06-MANIFEST)."""
import json
import shutil
from pathlib import Path

import pytest

import micro_case
from conftest import CLEAN, set_validity, share, write_config
from harness import manifest as records
from harness import run as harness_run
from harness import score
from harness.__main__ import main

WORLD = Path(__file__).resolve().parents[2].joinpath("data", "world")
R = score.rate

# Two hand-made runs of the micro world. In the second, A1/1 is an ESCALATE: no missed true match, and A1 agrees
# across framings.
RUNS = {"run-1": micro_case.lines(), "run-2": micro_case.lines({("A1", 1): ("ESCALATE", ["E1a"])})}
BOTH = score.set_figures(RUNS, micro_case.TRUTH)


# ---- pooled and spread, against literals

def test_the_pooled_figures_are_sums_over_the_runs():
    cell = BOTH["pooled"]["figures"]["overall"]
    assert cell["items"] == 36 and cell["missed_true_matches"] == 1 and cell["ambiguous_closed"] == 6
    assert cell["verdicts"] == {"CLOSE": 15, "ESCALATE": 21} and cell["failures"] == 8
    assert cell["over_escalation"] == R(10, 18) and cell["over_escalation_failures"] == R(6, 18)
    assert cell["citation_existence"] == R(24, 28) and cell["citation_accuracy"] == R(6, 8)
    assert cell["citation_precision"] == R(6, 10)
    assert cell["verdict_consistency"] == R(7, 12)  # consistent alert-runs over all alert-runs: 3 of 6, then 4 of 6
    assert BOTH["pooled"]["ac2"]["main"] == {"closes": 15, "valid": 13, "violations": 2}
    assert BOTH["pooled"]["injection"]["overall"]["pairs"] == 12 and BOTH["pooled"]["injection"]["overall"]["divergent"] == 8
    assert BOTH["pooled"]["figures"]["by_framing"]["1"]["missed_true_matches"] == 1
    assert BOTH["pooled"]["figures"]["by_family"]["name_variants"]["missed_true_matches"] == 1


def test_pooled_latency_is_over_all_main_items_of_the_runs():
    # each run's main items take 1 to 18 seconds: 36 values, nearest rank 18 for the median and 35 for p95
    assert BOTH["pooled"]["figures"]["overall"]["latency"]["wall_s"] == {"median": 9.0, "p95": 18.0}
    slow = {"run-1": micro_case.lines(), "run-2": [{**line, "wall_s": line["wall_s"] + 1000} for line in micro_case.lines()]}
    pooled = score.set_figures(slow, micro_case.TRUTH)["pooled"]["figures"]["overall"]["latency"]["wall_s"]
    assert pooled == {"median": 18.0, "p95": 1017.0}  # not the mean of the two runs' medians, 9 and 1009


def test_the_spread_gives_each_runs_value_with_the_minimum_and_maximum():
    cell = BOTH["spread"]["figures"]["overall"]
    assert cell["missed_true_matches"] == {"per_run": {"run-1": 1, "run-2": 0}, "min": 0, "max": 1}
    assert cell["ambiguous_closed"] == {"per_run": {"run-1": 3, "run-2": 3}, "min": 3, "max": 3}
    assert cell["verdict_consistency"] == {"per_run": {"run-1": R(3, 6), "run-2": R(4, 6)}, "min": R(3, 6), "max": R(4, 6)}
    assert cell["over_escalation"]["min"] == cell["over_escalation"]["max"] == R(5, 9)
    assert cell["latency"]["wall_s"]["median"] == {"per_run": {"run-1": 9.0, "run-2": 9.0}, "min": 9.0, "max": 9.0}
    assert cell["failures_by_kind"]["timeout"]["per_run"] == {"run-1": 1, "run-2": 1}
    assert BOTH["spread"]["figures"]["by_framing"]["1"]["missed_true_matches"]["max"] == 1
    assert BOTH["spread"]["injection"]["overall"]["divergent"] == {"per_run": {"run-1": 4, "run-2": 4}, "min": 4, "max": 4}


def test_rates_are_compared_as_exact_fractions_and_a_not_applicable_one_is_left_out():
    spread = score.spread({"a": R(1, 3), "b": R(2, 6), "c": R(333, 1000), "d": R(0, 0)})
    assert spread["min"] == R(333, 1000) and spread["max"] in (R(1, 3), R(2, 6))
    assert spread["per_run"]["d"]["not_applicable"] is True
    assert score.spread({"a": R(0, 0)}) == {"per_run": {"a": R(0, 0)}, "min": None, "max": None}
    assert score.spread({"a": None, "b": None}) == {"per_run": {"a": None, "b": None}, "min": None, "max": None}


def test_the_spread_has_the_same_shape_as_the_figures():
    def shape(tree, leaf):
        if isinstance(tree, dict) and not leaf(tree):
            return {key: shape(value, leaf) for key, value in tree.items()}
        return None
    figures = score.figures(micro_case.lines(), micro_case.TRUTH)
    assert shape(BOTH["spread"], lambda tree: "per_run" in tree) == shape(figures, lambda tree: "numerator" in tree)


# ---- which runs count, on real output folders

def copy_of(scored, folder):
    out = folder.joinpath("out")
    shutil.copytree(scored[0], out, ignore=shutil.ignore_patterns("report.json", "sets"))
    return out


def test_three_valid_runs_pool_and_make_the_set_eligible(scored):
    out, ids, done = scored
    report, = done["sets"].values()
    assert report == json.loads(json.dumps(report)) == json.loads(
        out.joinpath("sets", f"{report['run_set']}.json").read_text(encoding="utf-8"))
    assert report["valid_runs"] == 3 and report["eligible_as_baseline"] is True and report["superseded"] is None
    assert [(run["run_id"], run["state"], run["valid"], run["left_out_because"]) for run in report["runs"]] == [
        (run_id, "completed", True, []) for run_id in ids]
    one = done["reports"][ids[0]]["figures"]["overall"]
    pooled = report["pooled"]["figures"]["overall"]
    assert pooled["items"] == 5400 and pooled["missed_true_matches"] == 3 * one["missed_true_matches"] > 0
    for name in ("over_escalation", "citation_existence", "citation_accuracy", "verdict_consistency"):
        assert pooled[name] == R(3 * one[name]["numerator"], 3 * one[name]["denominator"])
    assert pooled["verdict_consistency"]["denominator"] == 1800  # all alert-runs
    spread = report["spread"]["figures"]["overall"]["missed_true_matches"]
    assert spread == {"per_run": dict.fromkeys(ids, one["missed_true_matches"]), "min": one["missed_true_matches"],
                      "max": one["missed_true_matches"]}
    assert "Summed over the valid runs" in report["notes"]["pooled"]


def test_dirty_infrastructure_invalid_aborted_and_unfinished_runs_are_listed_and_left_out(scored, tmp_path, monkeypatch):
    out, ids = copy_of(scored, tmp_path), scored[1]
    set_validity(out, ids[1], dirty=True)
    set_validity(out, ids[2], marked=True)
    # the same agent name, so the same run set: here the agent itself breaks on its first item
    monkeypatch.setitem(harness_run.AGENTS, "inprocess", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    aborted = harness_run.run(write_config(tmp_path), out)
    assert aborted["state"] == "aborted" and aborted["run_set"] == scored[2]["reports"][ids[0]]["run_set"]
    records.index_update(out, {"run_id": "never-finished", "run_set": aborted["run_set"], "state": "started",
                               "dirty": True, "infra_invalid": None, "cause": None, "rerun_cause": None, "calls": None,
                               "cost": None, "started_at": "2026-10-15T00:00:00+00:00"})  # as the run step writes it

    done = score.score_all(out, WORLD)
    report, = done["sets"].values()
    assert [(run["run_id"], run["valid"], run["left_out_because"]) for run in report["runs"]] == [
        (ids[0], True, []), (ids[1], False, ["dirty tree"]), (ids[2], False, ["infrastructure-invalid"]),
        (aborted["run_id"], False, ["aborted"]), ("never-finished", False, ["never finished"])]
    assert report["valid_runs"] == 1 and report["eligible_as_baseline"] is False
    assert report["pooled"]["figures"]["overall"]["items"] == 1800  # one run only
    assert list(report["spread"]["figures"]["overall"]["items"]["per_run"]) == [ids[0]]
    # the runs left out are still scored and published in full, with why they do not count
    assert sorted(done["reports"]) == sorted(ids)
    assert done["reports"][ids[1]]["validity"] == {"dirty": True, "infra_invalid": False, "valid": False}
    assert done["reports"][ids[2]]["validity"] == {"dirty": False, "infra_invalid": True, "valid": False}
    assert done["reports"][ids[1]]["figures"]["overall"]["items"] == 1800 == done["reports"][ids[2]]["figures"]["overall"]["items"]
    assert out.joinpath(ids[2], "report.json").is_file() and not out.joinpath(aborted["run_id"], "report.json").exists()


def test_a_run_that_is_both_dirty_and_infrastructure_invalid_names_both(scored, tmp_path):
    out, ids = copy_of(scored, tmp_path), scored[1]
    set_validity(out, ids[0], dirty=True, marked=True)
    report, = score.score_all(out, WORLD)["sets"].values()
    assert report["runs"][0]["left_out_because"] == ["dirty tree", "infrastructure-invalid"]
    assert report["valid_runs"] == 2 and report["eligible_as_baseline"] is False  # two valid runs are not enough


# ---- one clean commit of scoring code

def test_a_set_scored_by_dirty_code_needs_rescoring_and_is_not_eligible(scored, tmp_path, monkeypatch):
    out = copy_of(scored, tmp_path)
    monkeypatch.setattr(score, "scoring_state", lambda out: {"commit": CLEAN["commit"], "dirty": True})
    report, = score.score_all(out, WORLD)["sets"].values()
    assert report["valid_runs"] == 3 and report["rescore_needed"] is True and report["eligible_as_baseline"] is False
    monkeypatch.setattr(score, "scoring_state", lambda out: {"commit": None, "dirty": True})  # git could not answer
    report, = score.score_all(out, WORLD, rescore=True)["sets"].values()
    assert report["rescore_needed"] is True and report["eligible_as_baseline"] is False


def test_reports_from_two_commits_need_rescoring_and_one_clean_rescoring_makes_the_set_eligible(scored, tmp_path, monkeypatch):
    out, ids = tmp_path.joinpath("out"), scored[1]
    shutil.copytree(scored[0], out)  # with its three reports, written by the commit "ccc..."
    newer = {"commit": "d" * 40, "dirty": False}
    monkeypatch.setattr(score, "scoring_state", lambda out: dict(newer))
    done = score.score_all(out, WORLD)
    report, = done["sets"].values()
    assert done["written"] == [] and report["scored_by"] == newer
    assert [run["report_scored_by"] for run in report["runs"]] == [CLEAN] * 3
    assert report["rescore_needed"] is True and report["eligible_as_baseline"] is False

    out.joinpath(ids[0], "report.json").unlink()  # one report rewritten by the newer code, two still by the older
    report, = score.score_all(out, WORLD)["sets"].values()
    assert [run["report_scored_by"] for run in report["runs"]] == [newer, CLEAN, CLEAN]
    assert report["rescore_needed"] is True and report["eligible_as_baseline"] is False

    done = score.score_all(out, WORLD, rescore=True)
    report, = done["sets"].values()
    assert done["written"] == ids and [run["report_scored_by"] for run in report["runs"]] == [newer] * 3
    assert report["rescore_needed"] is False and report["eligible_as_baseline"] is True


def test_a_set_with_no_completed_run_does_not_ask_for_rescoring(tmp_path, monkeypatch, clean_scoring):
    monkeypatch.setitem(harness_run.AGENTS, "inprocess", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    harness_run.run(write_config(tmp_path), tmp_path.joinpath("out"))
    report, = score.score_all(tmp_path.joinpath("out"), WORLD)["sets"].values()
    assert report["rescore_needed"] is False and report["eligible_as_baseline"] is False and report["acceptance"] is None


# ---- superseding

@pytest.fixture(scope="module")
def two_sets_made_once(scored, tmp_path_factory):
    """Shared and read-only: the three scored runs, unscored again, with one run of a second run set beside
    them. Made once, because the extra run is what takes the time."""
    folder = tmp_path_factory.mktemp("two_sets")
    out = copy_of(scored, folder)
    other = harness_run.run(write_config(folder, infra_invalid_threshold="0.5"), out)
    return share(out), scored[2]["reports"][scored[1][0]]["run_set"], other["run_set"]


@pytest.fixture
def two_sets(two_sets_made_once, tmp_path):
    """This test's own copy of that folder, since superseding and scoring write into it:
    (output folder, set A, set B)."""
    out = tmp_path.joinpath("out")
    shutil.copytree(two_sets_made_once[0], out)
    return out, two_sets_made_once[1], two_sets_made_once[2]


def test_a_new_run_set_never_supersedes_an_old_one_by_itself(two_sets, clean_scoring):
    out, old, new = two_sets
    assert records.read_index(out)["sets"] == {}
    done = score.score_all(out, WORLD)
    assert done["sets"][old]["superseded"] is None and done["sets"][old]["eligible_as_baseline"] is True


def test_superseding_records_the_cause_and_ends_the_sets_eligibility(two_sets):
    out, old, new = two_sets
    records.supersede(out, old, new, "  the threshold was set too low  ")
    entry = records.read_index(out)["sets"]
    assert set(entry) == {old} and entry[old]["superseded_by"] == new and entry[old]["at"]
    assert entry[old]["cause"] == "the threshold was set too low"
    done = score.score_all(out, WORLD)
    assert done["sets"][old]["valid_runs"] == 3 and done["sets"][old]["eligible_as_baseline"] is False
    assert done["sets"][old]["superseded"] == entry[old] and done["sets"][new]["superseded"] is None
    assert len(records.read_index(out)["runs"]) == 4  # every run stays listed


@pytest.mark.parametrize("cause", ["", "   ", None, 5])
def test_superseding_needs_a_written_cause(two_sets, cause):
    out, old, new = two_sets
    try:
        records.supersede(out, old, new, cause)
        refusal = None
    except Exception as error:  # without the refusal, a later step may break on the cause instead: still no refusal
        refusal = error
    assert isinstance(refusal, ValueError) and "written cause" in str(refusal), \
        f"no refusal for a missing written cause: {refusal!r}"
    assert records.read_index(out)["sets"] == {}


def test_superseding_refuses_unknown_sets_itself_and_a_second_time(two_sets):
    out, old, new = two_sets
    with pytest.raises(ValueError, match="must have a run in the index"):
        records.supersede(out, old, "f" * 64, "cause")
    with pytest.raises(ValueError, match="must have a run in the index"):
        records.supersede(out, old[:8], new, "cause")  # a shortened ID is not accepted
    with pytest.raises(ValueError, match="cannot supersede itself"):
        records.supersede(out, old, old, "cause")
    records.supersede(out, old, new, "cause")
    for pair in ((old, new), (new, old)):
        with pytest.raises(ValueError, match="cannot be superseded again"):
            records.supersede(out, *pair, "another cause")
    assert set(records.read_index(out)["sets"]) == {old}


def test_a_run_in_a_superseded_set_is_refused_before_any_call(two_sets, tmp_path, monkeypatch):
    out, old, new = two_sets
    records.supersede(out, old, new, "the threshold was set too low")
    calls = []
    monkeypatch.setitem(harness_run.AGENTS, "inprocess", lambda *args: calls.append(args))  # same name, same run set
    before = sorted(path.name for path in out.iterdir())
    index = out.joinpath("index.json").read_bytes()
    with pytest.raises(harness_run.ConfigError, match="was superseded by .*the threshold was set too low"):
        harness_run.run(write_config(tmp_path), out)
    assert calls == [] and sorted(path.name for path in out.iterdir()) == before
    assert out.joinpath("index.json").read_bytes() == index
    monkeypatch.undo()
    assert harness_run.run(write_config(tmp_path, infra_invalid_threshold="0.5"), out)["state"] == "completed"  # set B still runs


def test_the_supersede_command(two_sets, capsys):
    out, old, new = two_sets
    with pytest.raises(SystemExit):
        main(["supersede", str(out), old, new])  # no --cause
    assert main(["supersede", str(out), old, new, "--cause", " "]) == 1 and "written cause" in capsys.readouterr().err
    assert records.read_index(out)["sets"] == {}
    assert main(["supersede", str(out), old, new, "--cause", "wrong price table"]) == 0
    assert records.read_index(out)["sets"][old]["cause"] == "wrong price table"
    assert main(["score", str(out), str(WORLD)]) == 0 and "wrote 4 reports, kept 0, for 2 run sets" in capsys.readouterr().out
    assert main(["score", str(out), str(WORLD)]) == 0 and "wrote 0 reports, kept 4, for 2 run sets" in capsys.readouterr().out
    assert main(["score", str(out), str(WORLD), "--rescore"]) == 0
    assert "wrote 4 reports, kept 0, for 2 run sets" in capsys.readouterr().out
