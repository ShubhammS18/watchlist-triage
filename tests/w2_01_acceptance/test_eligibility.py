"""W2-01: a run set whose inputs the check cannot verify is NOT ELIGIBLE and never passes (DEC-W2-01-ELIGIBILITY).
Each case starts from the passing oracle set or from an oracle set made with other files; its per-target results are
still worked out, and marked mechanism only."""
import json

import pytest

from harness import release_check

from conftest import FIXTURES, SOURCED, copy_set, make_set, rewrite


def a_call_with_no_token_counts(rows):
    row = next(row for row in rows if row["twin"])
    row["attempts"].append({"error": None, "input_tokens": None, "output_tokens": None, "model_id": "claude-haiku-5-5"})


def assert_not_eligible(result, reason):
    assert result["result"] == "NOT ELIGIBLE" and result["mechanism_only"] is True
    assert any(reason in why for why in result["not_eligible_because"]), result["not_eligible_because"]
    assert set(result["targets"]) == {*release_check.COUNTS, *release_check.RATES, "modelled_review_time"}


def test_a_changed_targets_file(oracle_set, tmp_path):
    changed = tmp_path.joinpath("release-targets.json")
    changed.write_bytes(release_check.TARGETS.read_bytes().replace(b'"numerator": 39,', b'"numerator": 40,'))
    result = release_check.check(oracle_set[0], oracle_set[1], targets_path=changed)
    assert_not_eligible(result, "the targets file is not the committed one")
    assert result["failed"] == []  # every target met, and still no pass


def test_a_world_that_is_not_the_frozen_world(oracle_set, monkeypatch):
    monkeypatch.setattr(release_check, "FROZEN_WORLD_HASH", "0" * 64)
    assert_not_eligible(release_check.check(oracle_set[0], oracle_set[1]), "the world is not the frozen world")


def test_fewer_than_three_valid_runs(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[0], dirty=True)
    assert_not_eligible(release_check.check(out, run_set), "2 valid runs, fewer than 3")


@pytest.mark.parametrize("name, reason", [("price_table", "the price table is a fixture"),
                                          ("modelled_time", "the modelled-time file is not the committed sourced one")])
def test_a_fixture_price_table_or_modelled_time_file(tmp_path, name, reason):
    out, run_set, _ = make_set(tmp_path, "oracle", **{name: FIXTURES[name]})
    result = release_check.check(out, run_set)
    assert_not_eligible(result, reason)
    # a fixture price table is also not the committed config/prices.json
    assert len(result["not_eligible_because"]) == (2 if name == "price_table" else 1) and result["failed"] == []


def test_a_sourced_price_table_that_is_not_the_committed_one(tmp_path):
    table = json.loads(SOURCED["price_table"].read_text(encoding="utf-8"))
    table["source"] = table.get("source", "") + " (a copy)"  # still sourced, but not the committed file
    copy = tmp_path.joinpath("prices.json")
    copy.write_text(json.dumps(table), encoding="utf-8")
    out, run_set, _ = make_set(tmp_path.joinpath("set"), "oracle", price_table=copy)
    result = release_check.check(out, run_set)
    assert_not_eligible(result, "a run's price table is not config/prices.json as committed at that run's commit")
    assert len(result["not_eligible_because"]) == 1 and result["failed"] == []


def test_a_price_table_git_cannot_read_at_the_run_commit(oracle_set, monkeypatch):
    assert release_check.committed_price_hash(None) is None
    monkeypatch.setattr(release_check, "PRICES", "config/no-such-prices.json")
    assert_not_eligible(release_check.check(oracle_set[0], oracle_set[1]), "a run's price table is not")


def test_a_cost_that_is_only_a_lower_bound(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[1], a_call_with_no_token_counts)
    assert_not_eligible(release_check.check(out, run_set), "some cost is only a lower bound")


def test_a_run_that_cannot_be_loaded(oracle_set, tmp_path):
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[2], lambda rows: rows[0]["result"].update(reason="changed after the run"), rehash=False)
    result = release_check.check(out, run_set)
    assert_not_eligible(result, "items.jsonl does not match the hash in its manifest")
    assert_not_eligible(result, "2 valid runs, fewer than 3")


def test_the_command_exits_0_only_on_pass(oracle_set, tmp_path, capsys):
    from harness.__main__ import main
    assert main(["acceptance", str(oracle_set[0]), oracle_set[1]]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "PASS"
    out, run_set, ids = copy_set(oracle_set, tmp_path)
    rewrite(out, ids[0], dirty=True)
    assert main(["acceptance", str(out), run_set]) == 1
    assert json.loads(capsys.readouterr().out)["result"] == "NOT ELIGIBLE"
