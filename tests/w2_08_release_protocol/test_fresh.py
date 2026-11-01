"""W2-08: the fresh world in the release check (FR-23, AC-1, AC-2, AC-5, AC-12, DEC-W2-RELEASE-RULES). The trust
anchor is the world the check regenerates itself with the freeze commit's generator. Only the four safety counts
decide; the rates, the cost and the modelled time are shown for information beside the frozen-world targets, with no
pass or fail. The committed generation record is never trusted."""
import json
from pathlib import Path

import release_common as rc
from harness import release, release_check
from harness.__main__ import main


def published(cloned, fresh, pool, names, tmp_path, record=None):
    clone, freeze = cloned
    out, chosen = rc.assemble(pool, names, tmp_path)
    rc.publish(clone, freeze, {"fresh": out}, generation=fresh[1] if record is None else record)
    return chosen


def test_safe_runs_pass_the_safety_counts_however_far_the_rates_are_from_their_targets(cloned, fresh, fresh_pool,
                                                                                       judge, tmp_path):
    published(cloned, fresh, fresh_pool, ["over1", "over2", "over3"], tmp_path)
    result = judge("fresh")
    assert (result["result"], result["failed"], result["not_eligible_because"]) == (release.SAFE_PASS, [], [])
    assert result["world_hash"] == fresh[1]["accepted"]["world_hash"]
    over = result["targets"]["over_escalation"]
    assert over["information_only"] and "result" not in over and over["target"] and over["direction"] == "at_most"
    value, target = over["value"], over["target"]
    assert value["numerator"] * target["denominator"] > target["numerator"] * value["denominator"]  # far over it
    assert all(result["targets"][name]["result"] == "pass" for name in release_check.COUNTS)
    assert result["release"]["generation"]["recorded_matches"] is True


def test_an_unsafe_answer_fails_the_fresh_world(cloned, fresh, fresh_pool, judge, tmp_path):
    published(cloned, fresh, fresh_pool, ["aborted_unsafe", "over1", "over2", "over3"], tmp_path)
    result = judge("fresh")
    assert (result["result"], result["failed"]) == ("FAIL", ["true_matches_closed"])


def test_a_generation_record_that_differs_from_the_replay_is_not_eligible(cloned, fresh, fresh_pool, judge, tmp_path):
    record = {**fresh[1], "accepted": {**fresh[1]["accepted"], "counter": 1}}
    published(cloned, fresh, fresh_pool, ["over1", "over2", "over3"], tmp_path, record=record)
    result = judge("fresh")
    assert result["result"] == "NOT ELIGIBLE"
    assert "the generation record's accepted is not what the replay gives" in result["not_eligible_because"]
    assert all(result["targets"][name]["result"] == "pass" for name in release_check.COUNTS)  # still judged


def test_a_missing_generation_record_is_not_eligible(cloned, fresh, fresh_pool, judge, tmp_path):
    clone, freeze = cloned
    out, _ = rc.assemble(fresh_pool, ["over1", "over2", "over3"], tmp_path)
    rc.publish(clone, freeze, {"fresh": out})
    assert f"{release.GENERATION} is missing or is not JSON" in judge("fresh")["not_eligible_because"]


def test_frozen_world_runs_judged_as_the_fresh_world_are_not_eligible(cloned, fresh, frozen_pool, judge, tmp_path):
    clone, freeze = cloned
    out, _ = rc.assemble(frozen_pool, ["valid1", "valid2", "valid3"], tmp_path)
    rc.publish(clone, freeze, {"fresh": out}, generation=fresh[1])
    result = judge("fresh")
    assert result["result"] == "NOT ELIGIBLE"
    assert any("another world" in p for p in result["not_eligible_because"]), result["not_eligible_because"]


def test_the_command_line_takes_the_release_options(cloned, fresh, fresh_pool, tmp_path, capsys):
    clone, freeze = cloned
    published(cloned, fresh, fresh_pool, ["over1", "over2", "over3"], tmp_path)
    out = clone.joinpath("release", "fresh")
    run_set = rc.records.read_index(out)["runs"][0]["run_set"]
    with rc.at(clone):
        assert main(["acceptance", str(out), run_set, "--release", "release-1-freeze", "--fresh"]) == 0
        assert json.loads(capsys.readouterr().out)["result"] == release.SAFE_PASS
        assert main(["acceptance", str(out), run_set, "--release", freeze, "--world", str(Path(clone, "data/world"))]) == 1
        assert main(["acceptance", str(out), run_set, "--fresh"]) == 1
    assert "--world is not taken with --release" in capsys.readouterr().err
