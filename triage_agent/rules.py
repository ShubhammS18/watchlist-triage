"""The rubric's rules that the structured fields settle, from docs/rubric.md v1.2 alone. Python standard library only.

Rubric, Identifiers: the decisive identifiers are date of birth and ID number. Each agrees (both sides hold it and
the values are the same), conflicts (both hold it and the values differ) or is unavailable (a side lacks it).
Rubric, What evidence is sufficient to close: an alert may be closed only when (1) a decisive identifier conflicts,
(2) no decisive identifier agrees and (3) no snippet links the customer to the listed person.

So the fields alone settle two cases. If (1) or (2) fails, the rubric can never close the alert: ESCALATE. If both
hold and the alert has no snippet, (3) holds too: CLOSE. Otherwise the close turns on what a snippet says, which only
reading it can tell: these rules do not decide, and the model is asked. Any item that is not a customer or watchlist
field counts as text to read, and two values for one decisive identifier on one side are left to the model too.
"""
DECISIVE = ("date_of_birth", "id_number")
SIDES = ("customer_field", "watchlist_field")


def _compare(items):
    """(decisive items by side, conflicting fields, agreeing fields, whether there is text to read), or None when one
    side holds two values for a decisive identifier."""
    sides, text = {kind: {} for kind in SIDES}, False
    for item in items:
        if item["kind"] not in SIDES:
            text = True
        elif item["field"] in DECISIVE:
            if item["field"] in sides[item["kind"]]:
                return None
            sides[item["kind"]][item["field"]] = item
    customer, watchlist = (sides[kind] for kind in SIDES)
    both = [field for field in DECISIVE if field in customer and field in watchlist]
    conflicting = [field for field in both if customer[field]["value"] != watchlist[field]["value"]]
    agreeing = [field for field in both if customer[field]["value"] == watchlist[field]["value"]]
    return sides, conflicting, agreeing, text


def close_citation(items):
    """(the ids of every conflicting decisive item, on both sides; the reason the fields give for a close)."""
    sides, conflicting, _, _ = _compare(items)
    cited = sorted(sides[kind][field]["id"] for field in conflicting for kind in SIDES)
    return cited, f"{' and '.join(conflicting)} conflict and no decisive identifier agrees"


def decide(items):
    """(recommendation, reason, cited ids) for payload items ({id, kind, field, value}), or None when the close turns
    on reading a snippet. A CLOSE cites the items of every conflicting decisive identifier, on both sides; an ESCALATE
    cites every decisive item present, or every item when there is none."""
    compared = _compare(items)
    if compared is None:
        return None
    sides, conflicting, agreeing, text = compared
    if agreeing or not conflicting:
        cited = sorted(item["id"] for side in sides.values() for item in side.values())
        cited = cited or sorted(item["id"] for item in items)
        why = (f"{' and '.join(agreeing)} agree" if agreeing else "no decisive identifier conflicts")
        return "ESCALATE", f"Rubric rule: {why}, so identity is not ruled out and the alert cannot be closed.", cited
    if text:
        return None
    cited, why = close_citation(items)
    return "CLOSE", f"Rubric rule: {why}, and there is no snippet, so identity is ruled out.", cited
