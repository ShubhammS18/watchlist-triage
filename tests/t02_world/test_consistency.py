"""Consistency of the committed world, and in-memory mutation tests showing which check catches which break.

The mutation tests change a deep copy of the loaded world. Nothing on disk is touched.
"""
import copy
from datetime import date, timedelta

import pytest

from checks import check_evidence_matches_records, check_labels, check_schema, check_twins, expected_field_items


# ---- the committed world passes every named check
def test_every_record_passes_the_schema(world):
    check_schema(world)


def test_field_evidence_equals_the_customer_and_watchlist_records(world):
    check_evidence_matches_records(world)


def test_every_present_record_field_has_exactly_one_evidence_item_and_there_are_no_extras(world):
    customers = {r["id"]: r for r in world["customers"]}
    entries = {r["id"]: r for r in world["watchlist"]}
    evidence = {r["id"]: r for r in world["evidence"]}
    checked = 0
    for alert in world["alerts"]:
        items = [evidence[i] for i in alert["evidence_item_ids"] if evidence[i]["kind"] != "snippet"]
        expected = expected_field_items(customers[alert["customer_id"]], entries[alert["watchlist_entry_id"]])
        assert len(items) == len(expected)                                     # no extra and no missing field items
        assert len({(i["kind"], i["field"], i["value"]) for i in items}) == len(items)
        single = [(i["kind"], i["field"]) for i in items if i["field"] != "alias"]
        assert len(set(single)) == len(single)                                 # one item per field
        checked += len(items)
    assert checked > 4000


def test_records_and_evidence_both_give_the_planted_label_for_all_600(world):
    assert check_labels(world) == 600


def test_every_twin_passes_the_twin_check(world):
    check_twins(world)


# ---- in-memory mutations: each break is caught by a named check
def changed(world):
    return copy.deepcopy(world)


def test_mutation_one_customer_birth_date_moved_by_one_day_is_caught_by_the_evidence_consistency_check(world):
    mutated = changed(world)
    used = {a["customer_id"] for a in mutated["alerts"]}
    customer = next(c for c in mutated["customers"] if c["id"] in used and "date_of_birth" in c)
    customer["date_of_birth"] = (date.fromisoformat(customer["date_of_birth"]) + timedelta(days=1)).isoformat()
    with pytest.raises(AssertionError, match="evidence differs from the records"):
        check_evidence_matches_records(mutated)
    check_schema(mutated)                               # still a valid record: only the consistency check sees it


def test_mutation_birth_date_changed_in_record_and_evidence_alike_is_caught_by_the_label_check(world):
    """Codex's consistent break: record and evidence agree with each other but no longer support the label."""
    mutated = changed(world)
    labels = {r["alert_id"]: r for r in mutated["labels"]}
    evidence = {r["id"]: r for r in mutated["evidence"]}
    customers = {r["id"]: r for r in mutated["customers"]}
    alert = next(a for a in mutated["alerts"] if labels[a["id"]]["recipe"] == "tm_contradictory")
    item = next(evidence[i] for i in alert["evidence_item_ids"]
                if evidence[i]["kind"] == "customer_field" and evidence[i]["field"] == "date_of_birth")
    moved = (date.fromisoformat(item["value"]) + timedelta(days=1)).isoformat()
    item["value"] = customers[alert["customer_id"]]["date_of_birth"] = moved
    check_evidence_matches_records(mutated)             # the two representations still agree with each other
    with pytest.raises(AssertionError, match=alert["id"]):
        check_labels(mutated)


def test_mutation_a_removed_required_field_is_caught_by_the_schema_check(world):
    for table in ("customers", "watchlist", "evidence", "alerts", "twins", "labels"):
        mutated = changed(world)
        del mutated[table][0]["source"]
        with pytest.raises(AssertionError, match="schema"):
            check_schema(mutated)


def test_mutation_an_evidence_item_for_a_field_the_record_lacks_is_caught(world):
    mutated = changed(world)
    alert = mutated["alerts"][0]
    extra = dict(next(e for e in mutated["evidence"] if e["id"] == alert["evidence_item_ids"][0]))
    extra.update(id="EVD-99999", kind="customer_field", field="passport_number", value="SYN-000000000")
    mutated["evidence"].append(extra)
    alert["evidence_item_ids"].append("EVD-99999")
    with pytest.raises(AssertionError, match="only in evidence"):
        check_evidence_matches_records(mutated)


def test_mutation_a_record_field_with_no_evidence_item_is_caught(world):
    mutated = changed(world)
    used = {a["customer_id"] for a in mutated["alerts"]}
    customer = next(c for c in mutated["customers"] if c["id"] in used)
    customer["passport_number"] = "SYN-000000000"
    with pytest.raises(AssertionError, match="only in records"):
        check_evidence_matches_records(mutated)


@pytest.mark.parametrize("edit", ["drop_an_item", "other_customer", "keep_the_injected_item"])
def test_mutation_an_edited_twin_is_caught_by_the_twin_check(world, edit):
    mutated = changed(world)
    twin = mutated["twins"][0]
    link = next(l for l in mutated["links"] if l["twin_alert_id"] == twin["id"])
    if edit == "drop_an_item":
        twin["evidence_item_ids"] = twin["evidence_item_ids"][:-1]
    elif edit == "other_customer":
        twin["customer_id"] = next(c["id"] for c in mutated["customers"] if c["id"] != twin["customer_id"])
    else:
        original = next(a for a in mutated["alerts"] if a["id"] == link["original_alert_id"])
        twin["evidence_item_ids"] = list(original["evidence_item_ids"])
    with pytest.raises(AssertionError, match=twin["id"]):
        check_twins(mutated)


def test_mutation_a_flipped_label_is_caught_by_the_label_check(world):
    mutated = changed(world)
    row = next(r for r in mutated["labels"] if r["label"] == "CLEAR_FALSE_POSITIVE")
    row["label"], row["correct_action"] = "TRUE_MATCH", "ESCALATE"
    with pytest.raises(AssertionError, match=row["alert_id"]):
        check_labels(mutated)
