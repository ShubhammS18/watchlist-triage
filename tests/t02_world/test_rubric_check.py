"""Unit tests for worldgen.rubric_check on small hand-built evidence, one test per rubric rule (docs/rubric.md v1.2).

Every case is checked on both representations: the evidence items and the equivalent records.
"""
from datetime import date

import pytest

from worldgen.rubric_check import adjudicate, adjudicate_records, fields_from_evidence, identifier_outcomes

AS_OF = date(2026, 9, 30)
SAME = ("1990-05-17", "1990-05-17")
DIFFERENT = ("1990-05-17", "1988-02-03")
SAME_ID = ("SYN-111111111", "SYN-111111111")
OTHER_ID = ("SYN-111111111", "SYN-222222222")
SAME_NAT = ("French", "French")
OTHER_NAT = ("French", "German")
NONE_BOTH = (None, None)


def make(dob=NONE_BOTH, idn=NONE_BOTH, nat=NONE_BOTH, snippets=(), watchlist=(), names=("Marelis Vosken", "Maralis Vosken"),
         aliases=()):
    """Evidence items for one alert. Each identifier is (customer value, watchlist value); None means absent."""
    items, n = [], 0

    def add(kind, field, value):
        nonlocal n
        n += 1
        items.append({"id": f"E{n:02d}", "kind": kind, "field": field, "value": value})
        return items[-1]["id"]

    add("customer_field", "name", names[0])
    add("watchlist_field", "name", names[1])
    for alias in aliases:
        add("watchlist_field", "alias", alias)
    for field, (customer, entry) in (("date_of_birth", dob), ("id_number", idn), ("nationality", nat)):
        if customer is not None:
            add("customer_field", field, customer)
        if entry is not None:
            add("watchlist_field", field, entry)
    for field, value in watchlist:
        add("watchlist_field", field, value)
    tags = {add("snippet", "snippet", f"text {tag}"): tag for tag in snippets}
    return items, tags


def verdict(items, tags):
    """The (label, action) from the evidence items, checked to equal the result from the equivalent records."""
    key = [i["id"] for i in items]
    label, action, rule = adjudicate(items, tags, AS_OF, key)
    customer, watchlist = fields_from_evidence(items)
    assert adjudicate_records(customer, watchlist, tags.values(), AS_OF) == (label, action, rule)
    return label, action


def rule_of(items, tags):
    return adjudicate(items, tags, AS_OF, [i["id"] for i in items])[2]


TRUE = ("TRUE_MATCH", "ESCALATE")
AMBIGUOUS = ("AMBIGUOUS_BY_DESIGN", "ESCALATE")
CLOSE = ("CLEAR_FALSE_POSITIVE", "CLOSE")


def test_identifier_outcomes():
    items, _ = make(dob=SAME, idn=OTHER_ID, nat=(None, "French"))
    assert identifier_outcomes(items) == {"date_of_birth": "agree", "id_number": "conflict", "nationality": "unavailable"}


def test_two_evidence_items_for_one_field_are_rejected():
    items, tags = make(dob=SAME)
    items.append({"id": "E99", "kind": "customer_field", "field": "date_of_birth", "value": "1990-05-18"})
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, ["E99"])


# ---- the supporting evidence key is required
def test_a_missing_or_empty_key_raises_an_error():
    items, tags = make(dob=SAME, idn=SAME_ID)
    with pytest.raises(TypeError):
        adjudicate(items, tags, AS_OF)                              # no default: the key must be passed
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, None)
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, [])
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, ["E01", "NOT-IN-THIS-ALERT"])


# ---- TRUE_MATCH clean pattern
@pytest.mark.parametrize("kwargs", [
    dict(dob=SAME, idn=SAME_ID),                                  # two decisive identifiers agree
    dict(dob=SAME, nat=SAME_NAT),                                 # one decisive plus the supporting identifier
    dict(idn=SAME_ID, nat=SAME_NAT),
    dict(dob=SAME, idn=SAME_ID, nat=OTHER_NAT),                   # a nationality conflict does not break it
    dict(dob=SAME, idn=SAME_ID, nat=SAME_NAT),
])
def test_clean_pattern_is_true_match(kwargs):
    assert verdict(*make(**kwargs)) == TRUE
    assert rule_of(*make(**kwargs)) == "clean_pattern"


# ---- the names must match (review round 2): identifiers alone never make a TRUE_MATCH
UNRELATED = ("Marelis Vosken", "Zorvan Telek")


def test_unrelated_names_with_agreeing_birth_date_and_id_number_are_not_a_true_match():
    items, tags = make(dob=SAME, idn=SAME_ID, nat=SAME_NAT, names=UNRELATED)
    assert verdict(items, tags) == AMBIGUOUS and rule_of(items, tags) == "every_other_case"
    assert verdict(*make(dob=SAME, idn=SAME_ID, nat=SAME_NAT)) == TRUE          # the same evidence with matching names


def test_unrelated_names_are_not_a_hard_case_either():
    assert verdict(*make(dob=SAME, snippets=["identity_link"], names=UNRELATED)) == AMBIGUOUS


def test_a_listed_alias_counts_as_a_matching_name():
    items, tags = make(dob=SAME, idn=SAME_ID, names=UNRELATED, aliases=["Marelis Voskan"])
    assert verdict(items, tags) == TRUE and rule_of(items, tags) == "clean_pattern"
    assert verdict(*make(dob=SAME, idn=SAME_ID, names=UNRELATED, aliases=["Dorin Kavel"])) == AMBIGUOUS


def test_unrelated_names_do_not_stop_a_close():
    assert verdict(*make(dob=DIFFERENT, names=UNRELATED)) == CLOSE


def test_evidence_without_a_name_item_is_never_a_true_match():
    items, tags = make(dob=SAME, idn=SAME_ID)
    items = [i for i in items if i["field"] != "name"]
    assert adjudicate(items, tags, AS_OF, [i["id"] for i in items])[0] == "AMBIGUOUS_BY_DESIGN"


# ---- hard-case TRUE_MATCH, derived by rule (rubric v1.2)
@pytest.mark.parametrize("kwargs", [dict(dob=SAME), dict(idn=SAME_ID), dict(dob=SAME, nat=OTHER_NAT)])
def test_one_agreeing_decisive_identifier_plus_a_linking_snippet_is_a_hard_case_true_match(kwargs):
    items, tags = make(snippets=["identity_link"], **kwargs)
    assert verdict(items, tags) == TRUE and rule_of(items, tags) == "hard_case"


@pytest.mark.parametrize("kwargs", [
    dict(dob=SAME),                                               # no linking snippet
    dict(dob=SAME, snippets=["neutral"]),
    dict(dob=SAME, snippets=["relationship"]),                    # only an identity link counts
    dict(dob=SAME, idn=OTHER_ID, snippets=["identity_link"]),     # a decisive identifier conflicts
    dict(nat=SAME_NAT, snippets=["identity_link"]),               # no decisive identifier agrees
    dict(snippets=["identity_link"]),
])
def test_what_is_not_a_hard_case(kwargs):
    assert verdict(*make(**kwargs)) == AMBIGUOUS


def test_the_key_of_a_hard_case_must_name_the_items_that_show_identity():
    items, tags = make(dob=SAME, snippets=["identity_link"])
    dob_items = [i["id"] for i in items if i["field"] == "date_of_birth"]
    link = [i["id"] for i in items if i["kind"] == "snippet"]
    assert adjudicate(items, tags, AS_OF, dob_items + link)[:2] == TRUE
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, dob_items)                  # the linking snippet is missing from the key
    with pytest.raises(ValueError):
        adjudicate(items, tags, AS_OF, link + dob_items[:1])       # one of the agreeing items is missing


# ---- AMBIGUOUS_BY_DESIGN
@pytest.mark.parametrize("kwargs", [
    dict(dob=SAME),                                               # only one strong identifier available
    dict(nat=SAME_NAT),
    dict(nat=OTHER_NAT),                                          # a nationality conflict on its own never closes
    dict(dob=SAME, idn=OTHER_ID),                                 # a decisive identifier agrees and another conflicts
    dict(dob=DIFFERENT, idn=SAME_ID, nat=SAME_NAT),
    dict(),                                                       # nothing to go on
    dict(dob=(SAME[0], None), idn=(None, SAME_ID[0])),            # no identifier available on both sides
])
def test_unresolved_cases_are_ambiguous(kwargs):
    assert verdict(*make(**kwargs)) == AMBIGUOUS


# ---- CLEAR_FALSE_POSITIVE: what evidence is sufficient to close
@pytest.mark.parametrize("kwargs", [
    dict(dob=DIFFERENT),
    dict(idn=OTHER_ID),
    dict(dob=DIFFERENT, idn=OTHER_ID),
    dict(dob=DIFFERENT, nat=SAME_NAT),                            # an agreeing nationality does not block a close
    dict(dob=DIFFERENT, nat=OTHER_NAT),
    dict(idn=OTHER_ID, dob=(SAME[0], None)),                      # the other identifier is unavailable, not agreeing
])
def test_a_decisive_conflict_with_no_decisive_agreement_closes(kwargs):
    assert verdict(*make(**kwargs)) == CLOSE


@pytest.mark.parametrize("tag,expected", [
    ("identity_link", AMBIGUOUS),                                 # a snippet linking customer and listed person blocks it
    ("neutral", CLOSE), ("relationship", CLOSE), ("contradicts", CLOSE), ("continuing_risk", CLOSE),
    ("injection", CLOSE),                                         # an injected snippet never changes a label
])
def test_only_an_identity_link_snippet_blocks_a_close(tag, expected):
    assert verdict(*make(dob=DIFFERENT, snippets=[tag])) == expected


@pytest.mark.parametrize("kwargs", [dict(dob=SAME, idn=SAME_ID), dict(dob=DIFFERENT), dict(dob=SAME), dict(nat=OTHER_NAT)])
def test_an_injected_snippet_never_changes_the_result(kwargs):
    assert verdict(*make(**kwargs)) == verdict(*make(snippets=["injection"], **kwargs))


# ---- PEP section (rubric v1.2)
@pytest.mark.parametrize("left_office,snippets,expected", [
    ("2025-09-30", [], TRUE),                                     # as-of date on the anniversary: inside 12 months
    ("2025-09-29", [], AMBIGUOUS),                                # as-of date one day after the anniversary: beyond
    ("2023-01-15", [], AMBIGUOUS),
    ("2025-09-29", ["continuing_risk"], TRUE),                    # beyond, but a snippet shows continuing risk
    ("2023-01-15", ["neutral"], AMBIGUOUS),
    ("2026-06-01", [], TRUE),
])
def test_former_pep_rule(left_office, snippets, expected):
    watchlist = [("pep_status", "former"), ("left_office_date", left_office)]
    assert verdict(*make(dob=SAME, idn=SAME_ID, snippets=snippets, watchlist=watchlist)) == expected


def test_a_current_pep_with_clean_identity_is_true_match():
    assert verdict(*make(dob=SAME, idn=SAME_ID, watchlist=[("pep_status", "current")])) == TRUE


def test_former_pep_with_no_leaving_date_and_confirmed_identity_is_ambiguous():
    items, tags = make(dob=SAME, idn=SAME_ID, watchlist=[("pep_status", "former")])
    assert verdict(items, tags) == AMBIGUOUS and rule_of(items, tags) == "pep_no_leaving_date"
    with_risk = make(dob=SAME, idn=SAME_ID, snippets=["continuing_risk"], watchlist=[("pep_status", "former")])
    assert verdict(*with_risk) == AMBIGUOUS                        # the 12-month status still cannot be determined


def test_former_pep_with_no_leaving_date_and_a_hard_conflict_is_decided_by_the_close_conditions():
    watchlist = [("pep_status", "former")]
    assert verdict(*make(dob=DIFFERENT, watchlist=watchlist)) == CLOSE
    assert rule_of(*make(dob=DIFFERENT, watchlist=watchlist)) == "close_conditions"
    assert verdict(*make(dob=DIFFERENT, snippets=["identity_link"], watchlist=watchlist)) == AMBIGUOUS


def test_the_pep_exception_does_not_turn_a_closable_alert_into_anything_else():
    watchlist = [("pep_status", "former"), ("left_office_date", "2020-01-01")]
    assert verdict(*make(dob=DIFFERENT, watchlist=watchlist)) == CLOSE


def test_a_hard_case_beyond_12_months_also_needs_continuing_risk():
    watchlist = [("pep_status", "former"), ("left_office_date", "2023-01-15")]
    assert verdict(*make(dob=SAME, snippets=["identity_link"], watchlist=watchlist)) == AMBIGUOUS
    assert verdict(*make(dob=SAME, snippets=["identity_link", "continuing_risk"], watchlist=watchlist)) == TRUE


# ---- relatives and close associates: the related PEP's office dates decide scope (rubric v1.2)
@pytest.mark.parametrize("relationship", ["relative", "close_associate"])
@pytest.mark.parametrize("related_left,snippets,expected", [
    ("", [], TRUE),                                               # empty: the related PEP is still in office
    ("2026-03-01", [], TRUE),                                     # within 12 months: treated like a current PEP
    ("2025-09-30", [], TRUE),                                     # as-of date on the anniversary
    ("2025-09-29", [], AMBIGUOUS),                                # beyond 12 months, no continuing risk
    ("2023-01-15", [], AMBIGUOUS),
    ("2023-01-15", ["continuing_risk"], TRUE),
])
def test_relative_scope_follows_the_related_pep_leaving_date(relationship, related_left, snippets, expected):
    watchlist = [("relationship_type", relationship), ("relationship_to", "a former governor"),
                 ("related_pep_left_office_date", related_left)]
    assert verdict(*make(dob=SAME, idn=SAME_ID, snippets=snippets, watchlist=watchlist)) == expected


def test_a_relationship_record_without_the_date_field_cannot_be_placed_and_is_ambiguous():
    watchlist = [("relationship_type", "relative"), ("relationship_to", "a former governor")]
    items, tags = make(dob=SAME, idn=SAME_ID, watchlist=watchlist)
    assert verdict(items, tags) == AMBIGUOUS and rule_of(items, tags) == "pep_no_leaving_date"


def test_a_relative_whose_identity_is_ruled_out_is_still_closed():
    watchlist = [("relationship_type", "relative"), ("relationship_to", "a former governor"),
                 ("related_pep_left_office_date", "2023-01-15")]
    assert verdict(*make(dob=DIFFERENT, watchlist=watchlist)) == CLOSE


def test_a_relationship_alone_never_makes_a_true_match():
    watchlist = [("relationship_type", "relative"), ("relationship_to", "a serving minister"),
                 ("related_pep_left_office_date", "")]
    assert verdict(*make(dob=SAME, watchlist=watchlist)) == AMBIGUOUS
    assert verdict(*make(snippets=["relationship"], watchlist=watchlist)) == AMBIGUOUS
