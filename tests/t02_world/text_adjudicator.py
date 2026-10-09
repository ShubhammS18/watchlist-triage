"""A second adjudicator: label an alert from what an agent can see, and nothing else.

It reads an alert's evidence items (field values and snippet TEXT). It never sees a snippet tag, a label or a
key, and it does not import worldgen.rubric_check. What a snippet says is decided by the keyword predicates
below, which follow the wording of docs/rubric.md v1.2. The tests require it to agree with every planted label,
so a label can only stand if the visible text supports it.
"""
import re
from datetime import date

from worldgen.matcher import names_match
from worldgen.pepdates import within_12_months

LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")
RISK_WORDS = ("influence", "control", "formal role")           # rubric: PEP status and dates
CURRENT_WORDS = ("serving", "sitting", "current")
RELATION_WORDS = re.compile(r"\b(spouse|sibling|child|partner|associate)\b")


def says_same_person(text, customer_name, listed_name):
    """The note names both the customer and the listed person and says they are the same person."""
    return customer_name in text and listed_name in text and re.search(r"\bsame (person|individual)\b", text) is not None


def says_continuing_risk(text):
    """rubric: the person still holds influence, control or a formal role linked to state functions after leaving office."""
    return any(word in text.lower() for word in RISK_WORDS)


def says_relationship(text):
    return RELATION_WORDS.search(text.lower()) is not None


def says_current_office(text):
    return any(re.search(rf"\b{word}\b", text.lower()) for word in CURRENT_WORDS)


def label_from_text(items, as_of, titles):
    """One of LABELS, from the alert's visible evidence items only."""
    customer, listed, aliases, notes = {}, {}, [], []
    for item in items:
        if item["kind"] == "snippet":
            notes.append(item["value"])
        elif item["field"] == "alias":
            aliases.append(item["value"])
        else:
            (customer if item["kind"] == "customer_field" else listed)[item["field"]] = item["value"]

    def state(field):
        if field not in customer or field not in listed:
            return "unavailable"
        return "agree" if customer[field] == listed[field] else "conflict"

    decisive = [state("date_of_birth"), state("id_number")]
    link = any(says_same_person(text, customer["name"], listed["name"]) for text in notes)
    # rubric: what evidence is sufficient to close
    if "conflict" in decisive and "agree" not in decisive and not link:
        return "CLEAR_FALSE_POSITIVE"

    names = any(names_match(customer["name"], name, titles) for name in [listed["name"], *aliases])
    strong = decisive.count("agree") + (state("nationality") == "agree")
    clean = strong >= 2 and "agree" in decisive
    hard_case = decisive.count("agree") == 1 and link
    if not names or "conflict" in decisive or not (clean or hard_case):
        return "AMBIGUOUS_BY_DESIGN"

    # rubric: PEP status and dates; relatives and close associates
    if listed.get("pep_status") == "former":
        left = listed.get("left_office_date")
    elif "relationship_type" in listed:
        left = listed.get("related_pep_left_office_date")
    else:
        left = ""                                                # not a former office-holder: nothing to count
    if left is None:
        return "AMBIGUOUS_BY_DESIGN"                            # no leaving date: the 12-month status is unknown
    if left and not within_12_months(date.fromisoformat(left), as_of):
        if not any(says_continuing_risk(text) for text in notes):
            return "AMBIGUOUS_BY_DESIGN"
    # A relationship told only by a note carries no office dates, so it is in scope only if the note says the
    # official holds office now.
    if any(says_relationship(text) and not says_current_office(text) for text in notes):
        return "AMBIGUOUS_BY_DESIGN"
    return "TRUE_MATCH"
