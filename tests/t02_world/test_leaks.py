"""Leak resistance: nothing easy to measure should give the label away. Tests run on the committed world."""
from collections import Counter
from datetime import date

from conftest import WORLD_DIR
from leak_tables import ADDRESS, GROUP_SIZES, NAME_FORMS, SNIPPET_COUNTS, largest_gap, tables
from worldgen import load_config

CONFIG = load_config()
AS_OF = date.fromisoformat(CONFIG["as_of_date"])
LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")


def alerts_by_label(by_alert):
    groups = {label: [] for label in LABELS}
    for data in by_alert.values():
        groups[data["label"]["label"]].append(data)
    return groups


def test_share_of_alerts_with_a_snippet_is_within_15_points_across_labels(by_alert):
    percent = {}
    for label, group in alerts_by_label(by_alert).items():
        with_snippet = sum(any(i["kind"] == "snippet" for i in d["items"]) for d in group)
        percent[label] = with_snippet * 100 // len(group)
    assert max(percent.values()) - min(percent.values()) <= 15, percent


def test_a_neutral_snippet_does_not_rule_out_any_label(by_alert):
    for label, group in alerts_by_label(by_alert).items():
        neutral = sum(any(d["tags"].get(i["id"]) == "neutral" for i in d["items"]) for d in group)
        assert neutral >= 1, (label, neutral)       # present in every label; how often still differs (a stated limit)


def test_leaving_office_offsets_are_spread_across_all_three_labels(by_alert):
    allowed = set(CONFIG["pep_offset_days"])
    for label, group in alerts_by_label(by_alert).items():
        offsets = [(AS_OF - date.fromisoformat(i["value"])).days
                   for d in group for i in d["items"] if i["field"] == "left_office_date"]
        assert set(offsets) <= allowed, label
        assert any(o <= 365 for o in offsets) and any(o >= 366 for o in offsets), (label, sorted(offsets))
        assert len(set(offsets)) >= 3, (label, sorted(set(offsets)))


def test_a_date_beyond_12_months_is_found_in_every_label(by_alert):
    """The 12-month boundary must not be a feature of one label: a date just beyond it appears with each label."""
    for label, group in alerts_by_label(by_alert).items():
        offsets = {(AS_OF - date.fromisoformat(i["value"])).days
                   for d in group for i in d["items"] if i["field"] == "left_office_date"}
        assert offsets & {366, 380, 540}, (label, sorted(offsets))


def test_alert_numbers_do_not_reveal_the_label(by_alert):
    order = [by_alert[f"ALT-{n:04d}"]["label"]["label"] for n in range(1, 601)]
    changes = sum(1 for a, b in zip(order, order[1:]) if a != b)
    assert changes >= 60, changes                                    # a sorted list would have 2
    true_positions = [n for n, label in enumerate(order, 1) if label == "TRUE_MATCH"]
    assert min(true_positions) < 150 and max(true_positions) > 450


def test_customer_and_entry_numbers_do_not_follow_the_alert_numbers(world):
    same = sum(1 for n, a in enumerate(world["alerts"], 1) if a["customer_id"] == f"CUS-{n:04d}")
    assert same < 30


def test_evidence_list_sizes_overlap_across_labels(by_alert):
    ranges = {label: (min(len(d["items"]) for d in group), max(len(d["items"]) for d in group))
              for label, group in alerts_by_label(by_alert).items()}
    for low, high in ranges.values():
        assert low <= 8 and high >= 12, ranges


def test_every_family_appears_with_both_actions_where_the_rubric_allows(world):
    seen = Counter((r["primary_family"], r["correct_action"]) for r in world["labels"])
    for family in ("name_variants", "common_name_collisions", "thin_identifiers", "pep_status"):
        assert seen[(family, "CLOSE")] == 30 and seen[(family, "ESCALATE")] == 12, family
    assert seen[("contradictory_evidence", "CLOSE")] == 0 and seen[("contradictory_evidence", "ESCALATE")] == 12


# ---- free choices: address relation and name form must not predict the label (limit: 15 percentage points)
def test_address_relation_is_within_15_points_between_any_two_labels():
    table = tables(WORLD_DIR)["address"]
    assert largest_gap(table, ADDRESS) <= 150, {label: dict(counter) for label, counter in table.items()}
    assert all(table[label][category] > 0 for label in LABELS for category in ADDRESS)


def test_name_form_is_within_15_points_between_any_two_labels():
    table = tables(WORLD_DIR)["name_form"]
    assert largest_gap(table, NAME_FORMS) <= 150, {label: dict(counter) for label, counter in table.items()}
    assert all(table[label][category] > 0 for label in LABELS for category in NAME_FORMS)


def test_the_gap_measure_itself_notices_a_skew():
    from collections import Counter as C

    skewed = {"TRUE_MATCH": C({"exact": 16, "via alias": 14}), "AMBIGUOUS_BY_DESIGN": C({"exact": 18, "via alias": 12}),
              "CLEAR_FALSE_POSITIVE": C({"exact": 386, "via alias": 154})}
    assert largest_gap(skewed, ("exact", "via alias")) > 150


def test_plain_alerts_also_carry_name_variants():
    """Leak policy: a spelling variant or an alias is not a sign of the name-variants family or of any label."""
    by_family = tables(WORLD_DIR)["name_form_by_family"]
    plain = by_family[("CLEAR_FALSE_POSITIVE", "plain")]
    assert plain["spelling edit"] > 50 and plain["via alias"] > 10 and plain["exact"] > 100


# ---- structural shortcuts from the first independent review: group size and snippet count
def test_watchlist_group_size_is_within_15_points_between_any_two_labels():
    table = tables(WORLD_DIR)["group_size"]
    assert largest_gap(table, GROUP_SIZES) <= 150, {label: dict(counter) for label, counter in table.items()}
    assert all(table[label]["3"] > 0 and table[label]["1 (alone)"] > 0 for label in LABELS)   # every label has shared and single entries


def test_snippet_count_buckets_are_within_15_points_between_any_two_labels():
    table = tables(WORLD_DIR)["snippet_count"]
    assert largest_gap(table, SNIPPET_COUNTS) <= 150, {label: dict(counter) for label, counter in table.items()}
    assert all(table[label][bucket] > 0 for label in LABELS for bucket in SNIPPET_COUNTS)


def test_the_old_group_and_snippet_skews_would_fail_these_tests():
    """The numbers Codex measured in round 1: reuse sizes 3 and 4 tied to the label, two snippets mostly on escalations."""
    from collections import Counter as C

    old_groups = {"TRUE_MATCH": C({"1 (alone)": 24, "4 or more": 6}), "AMBIGUOUS_BY_DESIGN": C({"1 (alone)": 24, "3": 6}),
                  "CLEAR_FALSE_POSITIVE": C({"1 (alone)": 510, "3": 12, "4 or more": 18})}
    assert largest_gap(old_groups, GROUP_SIZES) > 150
    old_snippets = {"TRUE_MATCH": C({"0": 14, "1": 6, "2 or more": 10}), "AMBIGUOUS_BY_DESIGN": C({"0": 15, "1": 10, "2 or more": 5}),
                    "CLEAR_FALSE_POSITIVE": C({"0": 270, "1": 264, "2 or more": 6})}
    assert largest_gap(old_snippets, SNIPPET_COUNTS) > 150


def test_an_alert_never_shows_the_same_snippet_text_twice(by_alert):
    for data in by_alert.values():
        texts = [i["value"] for i in data["items"] if i["kind"] == "snippet"]
        assert len(set(texts)) == len(texts), data["alert"]["id"]
