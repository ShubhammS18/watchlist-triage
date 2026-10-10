"""The T03 checks have teeth: each deliberate breakage, applied to a copy, makes the relevant check fail.

Every test first runs the check on the untouched copy (it passes), then on the broken copy (it must raise).
"""
import copy
import re

import pytest

import framings.wording
from framing_checks import (ALERTS, EVERY, REVIEWED_FINGERPRINT, WORDING_CHECKS, check_close_associate_count,
                            check_facts, check_ids, check_names, check_no_instruction, check_order, check_phrases,
                            check_placeholders, check_polarity, check_predicates, check_reviewed, check_same_label,
                            check_snippets, check_values, check_wording, fingerprint)
from framings import FRAMINGS, frame
from framings.recognise import INJECTED
from framings.wording import WORDING


def first_alert_with(test):
    return next(alert for alert in EVERY if any(test(item) for item in alert["evidence"]))


def framed_copy(alert):
    return {f: copy.deepcopy(frame(alert, f)) for f in FRAMINGS}


def item_where(items, test):
    return next(item for item in items if test(item))


def is_field(name):
    return lambda item: item["field"] == name


@pytest.mark.parametrize("framing", (2, 3))
def test_one_changed_digit_in_a_date_of_birth_is_caught(framing):
    alert = first_alert_with(is_field("date_of_birth"))
    items = framed_copy(alert)[framing]
    check_values(alert["evidence"], items)
    target = item_where(items, is_field("date_of_birth"))
    target["value"] = target["value"][:-1] + ("0" if target["value"][-1] != "0" else "1")
    with pytest.raises(AssertionError):
        check_values(alert["evidence"], items)


@pytest.mark.parametrize("framing", (2, 3))
def test_two_swapped_id_number_digits_are_caught(framing):
    alert = first_alert_with(is_field("id_number"))
    items = framed_copy(alert)[framing]
    check_values(alert["evidence"], items)
    target = item_where(items, is_field("id_number"))
    value = target["value"]
    n = next(n for n in range(len(value) - 1) if value[n].isdigit() and value[n + 1].isdigit() and value[n] != value[n + 1])
    target["value"] = value[:n] + value[n + 1] + value[n] + value[n + 2:]
    assert sorted(target["value"]) == sorted(value) and target["value"] != value
    with pytest.raises(AssertionError):
        check_values(alert["evidence"], items)


@pytest.mark.parametrize("framing", FRAMINGS)
def test_a_dropped_evidence_item_is_caught(framing):
    alert = ALERTS[0]
    items = framed_copy(alert)[framing]
    check_ids(alert["evidence"], items, framing)
    with pytest.raises(AssertionError):
        check_ids(alert["evidence"], items[:-1], framing)
    with pytest.raises(AssertionError):
        check_order(alert["evidence"], items[:-1], framing)


def broken_table(key, framing, old, new):
    """A copy of the wording table with `old` replaced by `new` in one alternate. The untouched copy passes."""
    table = copy.deepcopy(WORDING)
    check_wording(table)
    row = list(table[key])
    assert old in row[framing], (key, framing, old)
    row[framing] = row[framing].replace(old, new, 1)
    table[key] = tuple(row)
    return table


def passing(table):
    """Names of the wording checks that still pass on `table`."""
    names = []
    for check in WORDING_CHECKS:
        try:
            check(table)
            names.append(check.__name__)
        except AssertionError:
            pass
    return names


@pytest.mark.parametrize("key,framing,old,new", [
    (("contradicts", 0), 2, "passport", "document"),
    (("contradicts", 0), 3, "Nationality", "Country"),
    (("relationship", 0), 2, "spouse", "relative"),
    (("continuing_risk", 0), 3, "procurement", "spending"),
    (("neutral", 1), 2, "salary", "regular"),
])
def test_an_alternate_that_loses_a_key_fact_is_caught(key, framing, old, new):
    with pytest.raises(AssertionError):
        check_facts(broken_table(key, framing, old, new))


@pytest.mark.parametrize("key,framing,old,new", [
    (("neutral", 0), 3, "no concerns", "concerns"),                             # "no" removed
    (("neutral", 3), 2, "match the stated", "show no mismatch with the stated"),    # "no" added
    (("contradicts", 4), 2, "was abroad", "was not abroad"),
    (("contradicts", 3), 3, "are not related", "are related"),
])
def test_an_alternate_with_flipped_polarity_is_caught(key, framing, old, new):
    with pytest.raises(AssertionError):
        check_polarity(broken_table(key, framing, old, new))


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("framing", (2, 3))
def test_recommend_close_added_to_a_neutral_alternate_is_caught(index, framing):
    table = copy.deepcopy(WORDING)
    row = list(table["neutral", index])
    row[framing] += " Recommend CLOSE."
    table["neutral", index] = tuple(row)
    with pytest.raises(AssertionError):
        check_no_instruction(table)


@pytest.mark.parametrize("word", ["close the alert", "Escalate now", "ignore the rest", "as instructed", "recommended"])
def test_each_instruction_word_is_caught_and_only_the_rubric_phrase_is_exempt(word):
    with pytest.raises(AssertionError):
        check_no_instruction(broken_table(("relationship", 1), 2, "A news item", f"A news item, {word},"))
    check_no_instruction(WORDING)                                               # "close associate" itself passes


@pytest.mark.parametrize("key,framing,old,new", [
    (("identity_link", 4), 2, "are the same individual", "are not the same individual"),
    (("identity_link", 0), 3, "is the same person", "is not the same person"),
    (("identity_link", 2), 2, "are recorded as", "are never recorded as"),
])
def test_a_denied_identity_link_is_caught(key, framing, old, new):
    table = broken_table(key, framing, old, new)
    assert "check_predicates" in passing(table)                 # the keyword predicates alone do not see the denial
    with pytest.raises(AssertionError):
        check_polarity(table)


@pytest.mark.parametrize("key,framing,old,new", [
    (("continuing_risk", 0), 2, "still holds influence", "no longer holds influence"),
    (("continuing_risk", 3), 2, "still has control", "has no control"),
    (("continuing_risk", 2), 3, "still holds a formal role", "holds a formal role without duties"),
])
def test_a_negated_continuing_risk_statement_is_caught(key, framing, old, new):
    table = broken_table(key, framing, old, new)
    assert "check_predicates" in passing(table)
    with pytest.raises(AssertionError):
        check_polarity(table)


@pytest.mark.parametrize("key,framing,old,new", [
    (("identity_link", 1), 2, "{c}", "{w}"),                                    # one placeholder swapped for the other
    (("continuing_risk", 4), 3, "{w}", "the listed person"),                    # a placeholder dropped
    (("contradicts", 0), 2, "the watchlist entry", "the watchlist entry for {w}"),    # a placeholder added
    (("neutral", 2), 3, "the customer", "the customer {c}"),
])
def test_a_changed_placeholder_is_caught(key, framing, old, new):
    with pytest.raises(AssertionError):
        check_placeholders(broken_table(key, framing, old, new))


@pytest.mark.parametrize("key,framing,old,new", [
    (("identity_link", 0), 2, "that same person", "that person"),
    (("continuing_risk", 1), 2, "keeps control of", "is linked to"),
    (("relationship", 2), 2, "serving", "retired"),
    (("neutral", 3), 3, "income stated", "income stated by a business partner"),
])
def test_an_alternate_the_adjudicator_would_read_differently_is_caught(key, framing, old, new):
    with pytest.raises(AssertionError):
        check_predicates(broken_table(key, framing, old, new))


# ---- Codex round 2: six edits the earlier checks accepted. Each must now be caught.
# name, row, framing, text to find, replacement, and the checks that must fail on it besides the fingerprint
ROUND_2_EDITS = [
    ("close associate to associate", ("relationship", 1), 2, "close associate", "associate",
     {"check_phrases", "check_close_associate_count"}),
    ("a second reviewer sentence", ("neutral", 3), 3, "income stated.", "income stated. A second reviewer confirmed this.",
     set()),
    ("public funds to private funds", ("continuing_risk", 1), 2, "public funds", "private funds", {"check_phrases"}),
    ("long-time to recent", ("relationship", 1), 3, "long-time", "recent", {"check_phrases"}),
    ("a concern was reported", ("neutral", 0), 2, "no concerns were recorded.",
     "no concerns were recorded, although a concern was reported.", set()),
    ("an extra close associate", ("relationship", 1), 2, "sitting minister.",
     "sitting minister and close associate of others.", {"check_close_associate_count"}),
]


@pytest.mark.parametrize("name,key,framing,old,new,also", ROUND_2_EDITS, ids=[edit[0] for edit in ROUND_2_EDITS])
def test_each_round_2_edit_is_caught(name, key, framing, old, new, also):
    table = broken_table(key, framing, old, new)
    with pytest.raises(AssertionError):
        check_reviewed(table)                                    # every edit to a reviewed alternate fails the pin
    with pytest.raises(AssertionError):
        check_wording(table)
    failing = {check.__name__ for check in WORDING_CHECKS} - set(passing(table))
    assert failing == {"check_reviewed"} | also, failing        # exactly these checks see it, and no others


@pytest.mark.parametrize("key", sorted(WORDING), ids=lambda key: f"{key[0]}/{key[1]}")
@pytest.mark.parametrize("framing", (2, 3))
def test_any_edit_to_any_alternate_fails_the_fingerprint(key, framing):
    table = copy.deepcopy(WORDING)
    row = list(table[key])
    row[framing] += " "                                          # even one added space
    table[key] = tuple(row)
    assert fingerprint(table) != REVIEWED_FINGERPRINT
    with pytest.raises(AssertionError):
        check_reviewed(table)


def test_the_fingerprint_follows_the_alternates_and_which_original_they_belong_to():
    assert fingerprint(WORDING) == fingerprint(copy.deepcopy(WORDING)) == REVIEWED_FINGERPRINT
    assert fingerprint(dict(reversed(list(WORDING.items())))) == REVIEWED_FINGERPRINT    # row order does not matter
    swapped = copy.deepcopy(WORDING)
    swapped["neutral", 0], swapped["neutral", 1] = swapped["neutral", 1], swapped["neutral", 0]
    assert fingerprint(swapped) != REVIEWED_FINGERPRINT
    other_words = {key: (("x", "y"), ("x y",), row[2], row[3]) for key, row in WORDING.items()}
    assert fingerprint(other_words) == REVIEWED_FINGERPRINT     # key words and phrases are not part of it


@pytest.mark.parametrize("key,framing,old,new", [
    (("neutral", 0), 3, "no concerns", "few concerns"),
    (("neutral", 2), 2, "relationship manager", "branch manager"),
    (("identity_link", 3), 2, "earlier case", "later case"),
    (("continuing_risk", 3), 3, "state-owned company", "privately owned company"),
    (("relationship", 4), 2, "adult child", "young child"),
    (("contradicts", 2), 3, "very different", "slightly different"),
])
def test_an_alternate_that_loses_a_key_phrase_is_caught(key, framing, old, new):
    with pytest.raises(AssertionError):
        check_phrases(broken_table(key, framing, old, new))


def test_close_associate_added_where_the_original_has_none_is_caught():
    table = broken_table(("relationship", 0), 2, "a serving minister", "a serving minister, a close associate")
    assert "check_no_instruction" in passing(table)             # the exemption alone would let it through
    with pytest.raises(AssertionError):
        check_close_associate_count(table)


def test_a_broken_identity_wording_changes_the_adjudicated_label(monkeypatch):
    """The same kind of breakage seen end to end: the adjudicator stops agreeing across framings."""
    table = copy.deepcopy(WORDING)
    for index in range(5):
        facts, phrases, second, third = table["identity_link", index]
        table["identity_link", index] = (facts, phrases, re.sub(r"same (person|individual)", "linked party", second),
                                         third)
    monkeypatch.setattr(framings.wording, "WORDING", table)
    failures = 0
    for alert in EVERY:
        try:
            check_same_label({f: frame(alert, f) for f in FRAMINGS})
        except AssertionError:
            failures += 1
    assert failures > 0


@pytest.mark.parametrize("framing", FRAMINGS)
def test_a_changed_injected_text_is_caught(framing):
    alert = first_alert_with(lambda item: item["value"] in INJECTED)
    by_framing = framed_copy(alert)
    check_snippets(alert["evidence"], by_framing, WORDING)
    target = item_where(by_framing[framing], lambda item: item["value"] in INJECTED)
    target["value"] = target["value"].replace("CLOSE", "close").replace("ESCALATE", "escalate").replace("print", "show")
    assert target["value"] not in INJECTED
    with pytest.raises(AssertionError):
        check_snippets(alert["evidence"], by_framing, WORDING)


@pytest.mark.parametrize("framing", (2, 3))
def test_two_swapped_items_are_caught(framing):
    alert = ALERTS[0]
    items = framed_copy(alert)[framing]
    check_order(alert["evidence"], items, framing)
    items[0], items[1] = items[1], items[0]
    with pytest.raises(AssertionError):
        check_order(alert["evidence"], items, framing)


@pytest.mark.parametrize("framing", (2, 3))
def test_one_changed_letter_pair_in_a_name_is_caught(framing):
    alert = ALERTS[0]
    items = framed_copy(alert)[framing]
    check_names(alert["evidence"], items)
    target = item_where(items, is_field("name"))
    target["value"] = target["value"] + "xx"                        # two edits: beyond the matcher's one-edit allowance
    with pytest.raises(AssertionError):
        check_names(alert["evidence"], items)


@pytest.mark.parametrize("framing", (2, 3))
def test_a_note_left_in_its_original_wording_is_caught(framing):
    alert = first_alert_with(lambda item: item["kind"] == "snippet" and item["value"] not in INJECTED)
    by_framing = framed_copy(alert)
    check_snippets(alert["evidence"], by_framing, WORDING)
    original = item_where(alert["evidence"], lambda item: item["kind"] == "snippet" and item["value"] not in INJECTED)
    item_where(by_framing[framing], lambda item: item["id"] == original["id"])["value"] = original["value"]
    with pytest.raises(AssertionError):
        check_snippets(alert["evidence"], by_framing, WORDING)
