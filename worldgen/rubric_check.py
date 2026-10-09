"""Derive an alert's label and correct action by rule from docs/rubric.md v1.2.

Every label is derived from what the agent can see: the customer and watchlist fields and the snippets (through
their tags). Nothing here reads a planted label or a planted flag. The same rules run on two representations:
the evidence items (adjudicate) and the customer and watchlist records (adjudicate_records); both must agree.
Each rule cites the rubric section it implements. The "injection" tag is ignored: an injected snippet never
changes a label.
"""
from datetime import date

from .matcher import entry_matches, load_titles
from .pepdates import within_12_months

DECISIVE = ("date_of_birth", "id_number")          # rubric: Identifiers
STRONG = DECISIVE + ("nationality",)               # rubric: Identifiers (nationality is the supporting identifier)
PEP_FIELDS = ("pep_status", "office", "left_office_date", "relationship_type", "relationship_to",
              "related_pep_left_office_date")
ACTION = {"TRUE_MATCH": "ESCALATE", "AMBIGUOUS_BY_DESIGN": "ESCALATE", "CLEAR_FALSE_POSITIVE": "CLOSE"}


def outcomes(customer, watchlist):
    """rubric: Identifiers. For each strong identifier: agree, conflict, or unavailable (one or both sides lack it)."""
    result = {}
    for field in STRONG:
        if field not in customer or field not in watchlist:
            result[field] = "unavailable"
        else:
            result[field] = "agree" if customer[field] == watchlist[field] else "conflict"
    return result


def names_agree(customer, watchlist):
    """rubric: TRUE_MATCH pattern, "the names match". The matcher's rule; a listed alias is compared the same way."""
    if "name" not in customer or "name" not in watchlist:
        return False
    return entry_matches(customer["name"], watchlist, load_titles())


def pep_scope(watchlist, as_of):
    """rubric: PEP status and dates; Relatives and close associates. Returns "in_scope", "beyond" or "unknown".

    A former PEP is judged by their own leaving date. A relative or close associate (a record with a relationship
    type) is judged by the related PEP's leaving date; an empty value means the related PEP is still in office.
    A missing date means the 12-month status cannot be determined.
    """
    if watchlist.get("pep_status") == "former":
        left = watchlist.get("left_office_date")
    elif "relationship_type" in watchlist:
        left = watchlist.get("related_pep_left_office_date")
        if left == "":
            return "in_scope"
    else:
        return "in_scope"
    if not left:
        return "unknown"
    return "in_scope" if within_12_months(date.fromisoformat(left), as_of) else "beyond"


def decide(customer, watchlist, tags, as_of):
    """Return (label, rule name) from field values and the tags of the alert's snippets."""
    result = outcomes(customer, watchlist)
    agreeing_decisive = [f for f in DECISIVE if result[f] == "agree"]
    decisive_conflict = any(result[f] == "conflict" for f in DECISIVE)
    link = "identity_link" in tags
    risk = "continuing_risk" in tags

    # rubric: "What evidence is sufficient to close" and the CLEAR_FALSE_POSITIVE pattern. Checked first, so a hard
    # conflict that rules out identity is decided by the close conditions whatever the PEP dates say.
    if decisive_conflict and not agreeing_decisive and not link:
        return "CLEAR_FALSE_POSITIVE", "close_conditions"

    # rubric: TRUE_MATCH clean pattern (the names match, two or more strong identifiers agree, at least one
    # decisive, no decisive conflict). A nationality conflict does not break it.
    names = names_agree(customer, watchlist)
    clean = names and sum(result[f] == "agree" for f in STRONG) >= 2 and bool(agreeing_decisive) and not decisive_conflict
    # rubric: hard-case TRUE_MATCH (the names match, exactly one decisive identifier agrees, none conflicts, and a
    # snippet links the customer to the listed person).
    hard_case = names and not clean and len(agreeing_decisive) == 1 and not decisive_conflict and link
    if clean or hard_case:
        scope = pep_scope(watchlist, as_of)
        # rubric v1.2, PEP status and dates: with no leaving date the 12-month status cannot be determined.
        if scope == "unknown":
            return "AMBIGUOUS_BY_DESIGN", "pep_no_leaving_date"
        # rubric, PEP status and dates: beyond 12 months it is TRUE_MATCH only if a snippet shows continuing risk.
        if scope == "beyond" and not risk:
            return "AMBIGUOUS_BY_DESIGN", "pep_beyond_12_months"
        return "TRUE_MATCH", "clean_pattern" if clean else "hard_case"

    # rubric: "In every other case it is AMBIGUOUS_BY_DESIGN."
    return "AMBIGUOUS_BY_DESIGN", "every_other_case"


def fields_from_evidence(items):
    """({customer field: value}, {watchlist field: value}) from an alert's evidence items.

    Alias items are gathered into the watchlist side's `aliases` list, as in a watchlist record.
    """
    customer, watchlist = {}, {"aliases": []}
    for item in items:
        if item["kind"] == "snippet":
            continue
        if item["field"] == "alias":
            watchlist["aliases"].append(item["value"])
            continue
        side = customer if item["kind"] == "customer_field" else watchlist
        if item["field"] in side:
            raise ValueError(f"two evidence items for {item['kind']} {item['field']}")
        side[item["field"]] = item["value"]
    return customer, watchlist


def identifier_outcomes(items):
    return outcomes(*fields_from_evidence(items))


def adjudicate(items, tags, as_of, key_ids):
    """Label, correct action and rule name from an alert's EVIDENCE items.

    tags is {snippet evidence id: tag}. key_ids is the supporting evidence key and is required (rubric:
    Supporting evidence key): a missing or empty key, or one naming items outside the alert, raises ValueError.
    For a hard-case TRUE_MATCH the key must name the agreeing decisive items and the linking snippet.
    """
    if key_ids is None:
        raise ValueError("the supporting evidence key is required")
    ids = {item["id"] for item in items}
    if not key_ids or not set(key_ids) <= ids:
        raise ValueError("the supporting evidence key is empty or names items outside the alert")
    customer, watchlist = fields_from_evidence(items)
    snippet_tags = {item["id"]: tags[item["id"]] for item in items if item["kind"] == "snippet"}
    label, rule = decide(customer, watchlist, set(snippet_tags.values()), as_of)
    if rule == "hard_case":
        result = outcomes(customer, watchlist)
        needed = {i["id"] for i in items if i["kind"] != "snippet" and i["field"] in DECISIVE and result[i["field"]] == "agree"}
        needed |= {item_id for item_id, tag in snippet_tags.items() if tag == "identity_link"}
        if not needed <= set(key_ids):
            raise ValueError("the supporting evidence key of a hard-case TRUE_MATCH does not name the items that show identity")
    return label, ACTION[label], rule


def adjudicate_records(customer, watchlist, snippet_tags, as_of):
    """Label, correct action and rule name from the customer and watchlist RECORDS plus the alert's snippet tags."""
    label, rule = decide(customer, watchlist, set(snippet_tags), as_of)
    return label, ACTION[label], rule
