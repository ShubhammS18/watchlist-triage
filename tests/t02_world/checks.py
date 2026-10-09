"""Named consistency checks on a world held in memory.

Each check takes the world as {table name: list of records} (see conftest.TABLES) and raises AssertionError
with a message naming the first problem. The tests run them on the committed world, and the mutation tests
run them on changed in-memory copies to show which check catches which kind of break.
"""
from datetime import date

from worldgen import load_config
from worldgen.rubric_check import adjudicate, adjudicate_records
from worldgen.validate import validate

AS_OF = date.fromisoformat(load_config()["as_of_date"])
META = {"id", "as_of_date", "source", "version"}


def check_schema(world):
    """Every record in every table carries id, as_of_date, source and version with the right types."""
    for table, rows in world.items():
        for row in rows:
            problems = validate(row)
            assert not problems, f"schema: {table} {row.get('id')}: {problems}"


def expected_field_items(customer, entry):
    """The (kind, field, value) evidence items an alert must have for these two records: one per present field."""
    items = [("customer_field", f, v) for f, v in customer.items() if f not in META]
    items += [("watchlist_field", "alias", alias) for alias in entry["aliases"]]
    items += [("watchlist_field", f, v) for f, v in entry.items() if f not in META and f != "aliases"]
    return sorted(items)


def check_evidence_matches_records(world):
    """Field evidence equals the records: same values, exactly one item per present field, no extra items."""
    customers = {r["id"]: r for r in world["customers"]}
    entries = {r["id"]: r for r in world["watchlist"]}
    evidence = {r["id"]: r for r in world["evidence"]}
    for alert in world["alerts"] + world["twins"]:
        customer, entry = customers[alert["customer_id"]], entries[alert["watchlist_entry_id"]]
        items = [evidence[i] for i in alert["evidence_item_ids"]]
        actual = sorted((i["kind"], i["field"], i["value"]) for i in items if i["kind"] != "snippet")
        expected = expected_field_items(customer, entry)
        assert actual == expected, (f"evidence differs from the records in {alert['id']}: "
                                    f"only in evidence {sorted(set(actual) - set(expected))}, "
                                    f"only in records {sorted(set(expected) - set(actual))}")
        for item in items:
            if item["kind"] == "customer_field":
                assert item["record_id"] == customer["id"], f"{item['id']} points at the wrong customer"
            elif item["kind"] == "watchlist_field":
                assert item["record_id"] == entry["id"], f"{item['id']} points at the wrong watchlist entry"


def check_labels(world):
    """The rubric rules give the planted label twice over: from the evidence items and from the records."""
    customers = {r["id"]: r for r in world["customers"]}
    entries = {r["id"]: r for r in world["watchlist"]}
    evidence = {r["id"]: r for r in world["evidence"]}
    tags = {r["evidence_item_id"]: r["tag"] for r in world["tags"]}
    keys = {r["alert_id"]: r["evidence_item_ids"] for r in world["keys"]}
    labels = {r["alert_id"]: r for r in world["labels"]}
    assert len(world["alerts"]) == 600 and set(labels) == {a["id"] for a in world["alerts"]}, "labels do not cover the 600 alerts"
    derived = 0
    for alert in world["alerts"]:
        planted = (labels[alert["id"]]["label"], labels[alert["id"]]["correct_action"])
        items = [evidence[i] for i in alert["evidence_item_ids"]]
        from_evidence = adjudicate(items, tags, AS_OF, keys[alert["id"]])
        alert_tags = [tags[i["id"]] for i in items if i["kind"] == "snippet"]
        from_records = adjudicate_records(customers[alert["customer_id"]], entries[alert["watchlist_entry_id"]], alert_tags, AS_OF)
        assert from_evidence[:2] == planted, f"{alert['id']}: evidence gives {from_evidence[0]}, planted {planted[0]}"
        assert from_records[:2] == planted, f"{alert['id']}: records give {from_records[0]}, planted {planted[0]}"
        assert from_evidence == from_records, f"{alert['id']}: evidence and records disagree"
        derived += 1
    return derived


def check_twins(world):
    """Each control twin equals its original except for the injected item, and is not one of the 600."""
    alerts = {a["id"]: a for a in world["alerts"]}
    tags = {r["evidence_item_id"]: r["tag"] for r in world["tags"]}
    links = {l["twin_alert_id"]: l for l in world["links"]}
    assert len(world["twins"]) == 15 and set(links) == {t["id"] for t in world["twins"]}, "twins and links do not pair up"
    for twin in world["twins"]:
        assert twin["id"] not in alerts, f"{twin['id']} is also one of the 600"
        link = links[twin["id"]]
        original = alerts[link["original_alert_id"]]
        removed = link["removed_evidence_item_id"]
        assert tags.get(removed) == "injection", f"{twin['id']}: the removed item is not the injected one"
        assert set(twin) == set(original), f"{twin['id']}: different shape from its original"
        for field in set(twin) - {"id", "evidence_item_ids"}:
            assert twin[field] == original[field], f"{twin['id']}: {field} differs from its original"
        assert twin["evidence_item_ids"] == [i for i in original["evidence_item_ids"] if i != removed], \
            f"{twin['id']}: evidence differs from its original by more than the injected item"
