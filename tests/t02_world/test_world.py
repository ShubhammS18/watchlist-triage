"""Structure and content of the committed world in data/world."""
import json
import re
import unicodedata
from collections import Counter
from datetime import date

import pytest

from conftest import TABLES, WORLD_DIR
from worldgen import load_config, load_names
from worldgen.matcher import load_titles, match_all
from worldgen.plan import FAMILIES, HARD_FAMILIES
from worldgen.rubric_check import ACTION, DECISIVE, adjudicate, identifier_outcomes
from worldgen.snippets import TEMPLATES, render
from worldgen.rng import Stream
from worldgen.textutil import name_parts, within_one_edit
from worldgen.validate import validate

CONFIG = load_config()
COUNTS = CONFIG["counts"]
AS_OF = date.fromisoformat(CONFIG["as_of_date"])


# ---- counts
def test_there_are_600_alerts_with_the_decided_label_mix(world):
    assert len(world["alerts"]) == len(world["labels"]) == len(world["keys"]) == COUNTS["alerts"] == 600
    assert Counter(r["label"] for r in world["labels"]) == {
        "TRUE_MATCH": 30, "AMBIGUOUS_BY_DESIGN": 30, "CLEAR_FALSE_POSITIVE": 540}


@pytest.mark.parametrize("label", ["TRUE_MATCH", "AMBIGUOUS_BY_DESIGN"])
def test_six_per_family_for_true_match_and_ambiguous(world, label):
    assert Counter(r["primary_family"] for r in world["labels"] if r["label"] == label) == {f: 6 for f in FAMILIES}


def test_clear_false_positive_has_30_per_hard_family_and_420_plain(world):
    cfp = Counter(r["primary_family"] for r in world["labels"] if r["label"] == "CLEAR_FALSE_POSITIVE")
    assert cfp == {**{f: 30 for f in HARD_FAMILIES}, None: 420}
    assert sum(cfp.values()) == 540


def test_secondary_families_are_two_per_primary_family_and_only_on_true_match(world):
    rows = [r for r in world["labels"] if r["secondary_family"]]
    assert all(r["label"] == "TRUE_MATCH" for r in rows)
    assert Counter(r["primary_family"] for r in rows) == {f: 2 for f in FAMILIES}
    assert all(r["secondary_family"] != r["primary_family"] for r in rows)


def test_correct_actions_and_hard_case_flags(world):
    assert all(r["correct_action"] == ACTION[r["label"]] for r in world["labels"])
    hard = [r for r in world["labels"] if r["hard_case"]]
    assert len(hard) == 6 and {r["label"] for r in hard} == {"TRUE_MATCH"}
    assert {r["primary_family"] for r in hard} == {"thin_identifiers"}


def test_no_clear_false_positive_is_contradictory(world, by_alert):
    for row in world["labels"]:
        if row["label"] != "CLEAR_FALSE_POSITIVE":
            continue
        assert row["primary_family"] != "contradictory_evidence" and row["secondary_family"] is None
        data = by_alert[row["alert_id"]]
        outcomes = identifier_outcomes(data["items"])
        decisive = [outcomes[f] for f in DECISIVE]
        assert "agree" not in decisive and "conflict" in decisive      # a closable alert has nothing to contradict it
        assert "contradicts" not in {data["tags"].get(i["id"]) for i in data["items"]}


# ---- schema, format, references
def test_every_record_passes_the_schema_check(world):
    problems = [(name, r.get("id"), p) for name, rows in world.items() for r in rows for p in validate(r)]
    assert problems == []


@pytest.mark.parametrize("path", sorted(TABLES.values()))
def test_files_are_canonical_jsonl(path):
    raw = WORLD_DIR.joinpath(*path.split("/")).read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n") and "\r" not in text
    assert unicodedata.normalize("NFC", text) == text

    def refuse_float(value):
        raise AssertionError(f"float {value} in {path}")

    for line in text.split("\n")[:-1]:
        record = json.loads(line, parse_float=refuse_float)
        assert line == json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_ids_are_unique_and_follow_the_pattern(world):
    prefixes = {"customers": "CUS", "watchlist": "WLE", "evidence": "EVD", "alerts": "ALT", "labels": "LBL",
                "keys": "KEY", "tags": "TAG", "twins": "TWN", "links": "LNK"}
    for name, rows in world.items():
        ids = [r["id"] for r in rows]
        assert len(set(ids)) == len(ids)
        assert all(re.fullmatch(prefixes[name] + r"-[0-9]+", i) for i in ids)
        assert ids == sorted(ids)


def test_all_references_resolve(world):
    customers, entries = {c["id"] for c in world["customers"]}, {w["id"] for w in world["watchlist"]}
    evidence = {e["id"]: e for e in world["evidence"]}
    alert_ids = {a["id"] for a in world["alerts"]}
    seen = Counter()
    for alert in world["alerts"]:
        assert alert["customer_id"] in customers and alert["watchlist_entry_id"] in entries
        assert alert["evidence_item_ids"] and len(set(alert["evidence_item_ids"])) == len(alert["evidence_item_ids"])
        for item_id in alert["evidence_item_ids"]:
            item = evidence[item_id]
            assert item["alert_id"] == alert["id"]
            seen[item_id] += 1
            if item["kind"] == "customer_field":
                assert item["record_id"] == alert["customer_id"]
            elif item["kind"] == "watchlist_field":
                assert item["record_id"] == alert["watchlist_entry_id"]
            else:
                assert item["kind"] == "snippet" and "record_id" not in item
    assert set(seen) == set(evidence) and set(seen.values()) == {1}      # every evidence item is in exactly one alert
    assert {r["alert_id"] for r in world["labels"]} == {r["alert_id"] for r in world["keys"]} == alert_ids
    snippets = {i for i, e in evidence.items() if e["kind"] == "snippet"}
    assert {t["evidence_item_id"] for t in world["tags"]} == snippets and len(snippets) == len(world["tags"])
    assert {t["tag"] for t in world["tags"]} == {"neutral", "identity_link", "continuing_risk", "relationship",
                                                 "contradicts", "injection"}


def test_customers_and_watchlist_entries_are_used_as_planned(world):
    used_customers = Counter(a["customer_id"] for a in world["alerts"])
    used_entries = Counter(a["watchlist_entry_id"] for a in world["alerts"])
    assert len(world["customers"]) == 800 and len(used_customers) == 600 and set(used_customers.values()) == {1}
    assert len(world["watchlist"]) == 720 and len(used_entries) == 520
    assert len(world["customers"]) - len(used_customers) == COUNTS["background_customers"]
    assert len(world["watchlist"]) - len(used_entries) == COUNTS["background_watchlist_entries"]
    shared = [n for n in used_entries.values() if n > 1]
    assert len(shared) == 40 and set(shared) == {3} and sum(shared) == 120   # 40 entries shared by three alerts each


def test_keys_are_non_empty_and_inside_the_alert(by_alert):
    for data in by_alert.values():
        ids = {i["id"] for i in data["items"]}
        assert data["key"] and set(data["key"]) <= ids and len(set(data["key"])) == len(data["key"])


# ---- the rubric and the matcher
def test_rubric_check_agrees_with_every_planted_label(by_alert):
    """All 600 labels are derived by rule from the evidence; no planted flag is passed in."""
    rules = Counter()
    for alert_id, data in by_alert.items():
        planted = data["label"]
        label, action, rule = adjudicate(data["items"], data["tags"], AS_OF, data["key"])
        assert (label, action) == (planted["label"], planted["correct_action"]), (alert_id, planted["recipe"])
        assert planted["hard_case"] == (rule == "hard_case")       # the stored flag is a result, not an input
        rules[rule] += 1
    assert sum(rules.values()) == 600
    assert rules == {"close_conditions": 540, "clean_pattern": 24, "hard_case": 6, "pep_beyond_12_months": 3,
                     "every_other_case": 27}


def test_a_hard_case_is_derived_by_rule_and_its_key_must_name_the_identity_items(by_alert):
    data = next(d for d in by_alert.values() if d["label"]["hard_case"])
    assert adjudicate(data["items"], data["tags"], AS_OF, data["key"]) == ("TRUE_MATCH", "ESCALATE", "hard_case")
    link = next(i["id"] for i in data["items"] if data["tags"].get(i["id"]) == "identity_link")
    with pytest.raises(ValueError):
        adjudicate(data["items"], data["tags"], AS_OF, [k for k in data["key"] if k != link])
    with pytest.raises(ValueError):
        adjudicate(data["items"], data["tags"], AS_OF, None)
    without_link = [i for i in data["items"] if i["id"] != link]
    assert adjudicate(without_link, data["tags"], AS_OF, [k for k in data["key"] if k != link])[0] == "AMBIGUOUS_BY_DESIGN"


def test_a_linking_snippet_blocks_a_close_in_two_ambiguous_alerts(by_alert):
    """New recipe: a decisive identifier conflicts, none agrees, and an identity_link snippet blocks the close."""
    found = [d for d in by_alert.values() if d["label"]["recipe"] == "am_contradictory_link"]
    assert len(found) == 2
    for data in found:
        assert data["label"]["label"] == "AMBIGUOUS_BY_DESIGN" and data["label"]["primary_family"] == "contradictory_evidence"
        assert not data["label"]["hard_case"]
        decisive = [identifier_outcomes(data["items"])[f] for f in DECISIVE]
        assert decisive.count("conflict") == 1 and "agree" not in decisive
        links = [i["id"] for i in data["items"] if data["tags"].get(i["id"]) == "identity_link"]
        assert len(links) == 1 and links[0] in data["key"]
        assert adjudicate(data["items"], data["tags"], AS_OF, data["key"]) == ("AMBIGUOUS_BY_DESIGN", "ESCALATE", "every_other_case")
        without = [i for i in data["items"] if i["id"] != links[0]]
        key = [k for k in data["key"] if k != links[0]]
        assert adjudicate(without, data["tags"], AS_OF, key)[:2] == ("CLEAR_FALSE_POSITIVE", "CLOSE")


def test_matcher_output_equals_the_planted_alerts(world):
    planted = sorted((a["customer_id"], a["watchlist_entry_id"]) for a in world["alerts"])
    assert len(set(planted)) == 600
    assert match_all(world["customers"], world["watchlist"], load_titles()) == planted


def test_relationship_records_carry_the_related_pep_leaving_date(world):
    """rubric v1.2: the related PEP's office dates decide scope. Empty means that PEP is still in office."""
    related = [w for w in world["watchlist"] if "relationship_type" in w]
    assert len(related) >= 4
    values = []
    for entry in related:
        assert "related_pep_left_office_date" in entry and "relationship_to" in entry
        value = entry["related_pep_left_office_date"]
        values.append(value)
        if value:
            assert date.fromisoformat(value) <= AS_OF
    assert "" in values and any(values)                               # both a serving and a former related PEP occur
    assert not [w for w in world["watchlist"] if "related_pep_left_office_date" in w and "relationship_type" not in w]


def test_relationship_prose_never_says_serving_next_to_a_past_leaving_date(world):
    """Review round 2: the wording of relationship_to is derived from the related PEP's status."""
    from worldgen.build import RELATED_ROLES, related_to

    seen = Counter()
    for entry in world["watchlist"]:
        if "relationship_to" not in entry:
            continue
        words, left = entry["relationship_to"].split(), entry["related_pep_left_office_date"]
        in_office = left == ""
        assert ("serving" in words) == in_office and ("former" in words) == (not in_office), entry["id"]
        assert "sitting" not in words and "current" not in words
        assert entry["relationship_to"] in {related_to(role, in_office) for role in RELATED_ROLES}
        seen[in_office] += 1
    assert seen[True] >= 1 and seen[False] >= 1
    for alert_item in world["evidence"]:                              # the evidence shows the same prose
        if alert_item["field"] == "relationship_to":
            assert alert_item["value"].split()[1] in ("serving", "former")
    assert related_to("minister", True) == "a serving minister" and related_to("minister", False) == "a former minister"


# ---- synthetic-only content
def test_every_name_part_comes_from_the_lists(world):
    lists = {p.lower() for f in ("given.txt", "family.txt") for p in load_names(f)}
    for entry in world["watchlist"]:
        for name in [entry["name"], *entry["aliases"]]:
            assert set(name_parts(name)) <= lists, name              # watchlist names are exact list parts
    for customer in world["customers"]:
        parts = name_parts(customer["name"], load_titles())
        assert len(parts) == 2, customer["name"]
        for part in parts:                                           # customer names may be spelling variants
            assert any(within_one_edit(part, known) for known in lists), customer["name"]


def test_id_numbers_use_the_synthetic_format(world):
    numbers = [r["id_number"] for r in world["customers"] + world["watchlist"] if "id_number" in r]
    assert len(numbers) > 1000
    assert all(re.fullmatch(r"SYN-[0-9]{9}", n) and n.startswith(CONFIG["id_prefix"]) for n in numbers)


def test_dates_of_birth_are_valid_dates_from_1950_to_2000(world):
    dates = [date.fromisoformat(r["date_of_birth"]) for r in world["customers"] + world["watchlist"] if "date_of_birth" in r]
    assert len(dates) > 1000
    assert all(date(1950, 1, 1) <= d <= date(2000, 12, 31) for d in dates)


def test_leaving_office_dates_are_valid_and_not_after_the_as_of_date(world):
    dates = [date.fromisoformat(r["left_office_date"]) for r in world["watchlist"] if "left_office_date" in r]
    assert dates and all(d <= AS_OF for d in dates)
    assert all(r["as_of_date"] == CONFIG["as_of_date"] for rows in world.values() for r in rows)


def test_nationalities_are_real_adjectives_from_the_fixed_set(world):
    from worldgen.build import NATIONALITIES

    found = {r["nationality"] for r in world["customers"] + world["watchlist"] if "nationality" in r}
    assert found <= set(NATIONALITIES) and len(found) > 20


def test_no_agent_visible_record_carries_a_label_or_key_field(world):
    forbidden = {"label", "correct_action", "primary_family", "secondary_family", "hard_case", "recipe", "tag",
                 "injection", "original_alert_id", "twin_alert_id"}
    for name in ("customers", "watchlist", "evidence", "alerts", "twins"):
        for record in world[name]:
            assert not forbidden & set(record)


# ---- snippets
def test_every_snippet_template_and_every_rendered_snippet_is_under_25_words(world):
    sample = Stream(1, "templates")
    for tag, templates in TEMPLATES.items():
        assert len(templates) >= 4 and len(set(templates)) == len(templates)
        for template in templates:
            assert len(template.format(c="Dr. Marelis Vosken", w="Zorvan Telek").split()) < 25, template
    for item in world["evidence"]:
        if item["kind"] == "snippet":
            assert 5 <= len(item["value"].split()) < 25, item["value"]
    assert render("neutral", sample, "A B", "C D") in TEMPLATES["neutral"]
