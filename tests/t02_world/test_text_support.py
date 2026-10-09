"""The visible TEXT must support every label (review round 2, finding 2).

Template wording is checked against the rubric's words, and a second adjudicator that sees no snippet tag
(text_adjudicator.py) must give the planted label for every alert and every control twin.
"""
from collections import Counter
from datetime import date

import pytest

from text_adjudicator import (CURRENT_WORDS, RISK_WORDS, label_from_text, says_continuing_risk, says_current_office,
                              says_relationship, says_same_person)
from worldgen import load_config
from worldgen.matcher import load_titles
from worldgen.snippets import INJECTED_TEXTS, TEMPLATES

AS_OF = date.fromisoformat(load_config()["as_of_date"])
TITLES = load_titles()
C, W = "Dr. Marelis Vosken", "Zorvan Telek"


def rendered(tag, customer=C, listed=W):
    return [template.format(c=customer, w=listed) for template in TEMPLATES[tag]]


# ---- template wording
@pytest.mark.parametrize("template", TEMPLATES["continuing_risk"])
def test_every_continuing_risk_template_uses_the_rubric_words(template):
    assert any(word in template.lower() for word in RISK_WORDS), template        # influence, control or formal role
    assert "office" in template and "{w}" in template                            # after leaving office, about the listed person
    assert any(word in template for word in ("still", "keeps")), template


@pytest.mark.parametrize("template", TEMPLATES["relationship"])
def test_every_relationship_template_states_a_current_office(template):
    assert any(word in template.split() for word in CURRENT_WORDS), template     # serving, sitting or current
    assert "former" not in template.lower() and "{w}" in template


@pytest.mark.parametrize("template", TEMPLATES["identity_link"])
def test_every_identity_link_template_names_the_customer_and_the_listed_person(template):
    assert "{c}" in template and "{w}" in template


# ---- the predicates recognise their own templates and nothing else
def test_each_predicate_accepts_every_template_of_its_tag():
    assert all(says_same_person(text, C, W) for text in rendered("identity_link"))
    assert all(says_continuing_risk(text) for text in rendered("continuing_risk"))
    assert all(says_relationship(text) and says_current_office(text) for text in rendered("relationship"))


@pytest.mark.parametrize("customer,listed", [(C, W), (W, W)])                    # also when both names are identical
def test_no_other_text_triggers_a_predicate(customer, listed):
    others = {tag: rendered(tag, customer, listed) for tag in TEMPLATES}
    others["injection"] = [text for _, text in INJECTED_TEXTS]
    for tag, texts in others.items():
        for text in texts:
            assert says_same_person(text, customer, listed) == (tag == "identity_link"), text
            assert says_continuing_risk(text) == (tag == "continuing_risk"), text
            assert says_relationship(text) == (tag == "relationship"), text


# ---- the second adjudicator agrees with every planted label
def test_the_text_adjudicator_agrees_with_all_600_planted_labels(by_alert):
    wrong = [(alert_id, d["label"]["label"]) for alert_id, d in by_alert.items()
             if label_from_text(d["items"], AS_OF, TITLES) != d["label"]["label"]]
    assert wrong == [] and len(by_alert) == 600
    assert Counter(label_from_text(d["items"], AS_OF, TITLES) for d in by_alert.values()) == {
        "TRUE_MATCH": 30, "AMBIGUOUS_BY_DESIGN": 30, "CLEAR_FALSE_POSITIVE": 540}


def test_the_text_adjudicator_agrees_on_every_control_twin(world, by_alert):
    evidence = {e["id"]: e for e in world["evidence"]}
    original = {l["twin_alert_id"]: l["original_alert_id"] for l in world["links"]}
    for twin in world["twins"]:
        items = [evidence[i] for i in twin["evidence_item_ids"]]
        assert label_from_text(items, AS_OF, TITLES) == by_alert[original[twin["id"]]]["label"]["label"]


# ---- it has teeth: the two wordings the review found unsupported no longer give TRUE_MATCH
def swap_snippet(data, tag, text):
    items = [dict(i) for i in data["items"]]
    target = next(i for i in items if data["tags"].get(i["id"]) == tag)
    target["value"] = text
    return items


def test_payments_that_merely_continue_do_not_show_continuing_risk(by_alert):
    data = next(d for d in by_alert.values() if d["label"]["recipe"] == "tm_pep_former_beyond_risk")
    assert label_from_text(data["items"], AS_OF, TITLES) == "TRUE_MATCH"
    old = "Ongoing investigation: payments from firms tied to Zorvan Telek continue after the end of their term."
    assert label_from_text(swap_snippet(data, "continuing_risk", old), AS_OF, TITLES) == "AMBIGUOUS_BY_DESIGN"


def test_a_note_about_a_former_office_holder_without_dates_is_not_in_scope(by_alert):
    data = next(d for d in by_alert.values() if d["label"]["recipe"] == "tm_pep_associate_snippet")
    assert label_from_text(data["items"], AS_OF, TITLES) == "TRUE_MATCH"
    old = "Press profile: Zorvan Telek is the adult child of a former head of a state agency."
    assert label_from_text(swap_snippet(data, "relationship", old), AS_OF, TITLES) == "AMBIGUOUS_BY_DESIGN"


def test_removing_the_linking_note_from_a_hard_case_makes_it_ambiguous(by_alert):
    data = next(d for d in by_alert.values() if d["label"]["hard_case"])
    assert label_from_text(data["items"], AS_OF, TITLES) == "TRUE_MATCH"
    rest = [i for i in data["items"] if data["tags"].get(i["id"]) != "identity_link"]
    assert label_from_text(rest, AS_OF, TITLES) == "AMBIGUOUS_BY_DESIGN"
