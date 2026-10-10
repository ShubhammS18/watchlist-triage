"""Shared data and checks for the T03 tests: the 600 alerts and 15 control twins in all three framings.

Each check raises AssertionError when a framing breaks its rule. The tests run them over the whole world, and
the mutation tests run them over deliberately broken copies to show that they fail.
"""
import hashlib
import json
import re
import string
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.joinpath("t02_world")))    # for text_adjudicator

from text_adjudicator import (label_from_text, says_continuing_risk, says_current_office,    # noqa: E402
                              says_relationship, says_same_person)

from framings import FRAMINGS, NAME_FIELDS, frame                                         # noqa: E402
from framings.recognise import INJECTED, which_original                                   # noqa: E402
from worldgen import load_config                                                          # noqa: E402
from worldgen.harness_twins import load_twins                                             # noqa: E402
from worldgen.loader import load_alerts                                                   # noqa: E402
from worldgen.matcher import load_titles, names_match                                     # noqa: E402
from worldgen.snippets import TEMPLATES                                                   # noqa: E402
from worldgen.textutil import name_parts                                                  # noqa: E402

AS_OF = date.fromisoformat(load_config()["as_of_date"])
TITLES = load_titles()
ALERTS, TWINS = load_alerts(), load_twins()
EVERY = ALERTS + TWINS                                           # twins come only from worldgen.harness_twins
BY_ID = {alert["id"]: alert for alert in EVERY}

ORIGINALS = {(tag, index): text for tag, templates in TEMPLATES.items() for index, text in enumerate(templates)}
NEGATION = re.compile(r"\b(no|not|never|nothing|none|without|neither|nor)\b", re.IGNORECASE)
INSTRUCTION_WORDS = ("recommend", "close", "escalate", "ignore", "instruct")     # refused anywhere in a line
EXEMPT_PHRASE = "close associate"                                # the rubric's own term; owner ruling 2026-10-09
# SHA-256 of the 50 alternates as the owner reviewed them (DEC-T03-WORDING-REVIEW-2). See `fingerprint`.
REVIEWED_FINGERPRINT = "89614485eaba8678bdc3d8a39fa2b45b47b482c3ed83c30bd0dc5ab45e2962cf"
C, W = "Dr. MARELIS, Vosken", "Hon Telek Zorvan"                 # three-token names, one in each new format


def frame_all():
    """{(alert id, framing): framed items} for every alert and twin."""
    return {(alert["id"], framing): frame(alert, framing) for alert in EVERY for framing in FRAMINGS}


def own_names(items):
    """(customer name, listed name) as written in these items."""
    return tuple(next(i["value"] for i in items if i["kind"] == kind and i["field"] == "name")
                 for kind in ("customer_field", "watchlist_field"))


def notes(items):
    """{evidence id: text} for the notes among these items."""
    return {i["id"]: i["value"] for i in items if i["kind"] == "snippet"}


# ---- ids
def check_ids(original, framed, framing):
    assert sorted(i["id"] for i in framed) == sorted(i["id"] for i in original)
    assert len({i["id"] for i in framed}) == len(framed)
    if framing == 1:
        assert framed == original


# ---- values that must not change
def check_values(original, framed):
    before = {i["id"]: i for i in original}
    for item in framed:
        source = before[item["id"]]
        if item["kind"] == "snippet" or item["field"] in NAME_FIELDS:
            assert {k: v for k, v in item.items() if k != "value"} == {k: v for k, v in source.items() if k != "value"}
        else:
            assert item == source, (item, source)


# ---- names
def check_names(original, framed):
    before = {i["id"]: i["value"] for i in original}
    for item in framed:
        if item["kind"] != "snippet" and item["field"] in NAME_FIELDS:
            old, new = before[item["id"]], item["value"]
            assert sorted(name_parts(new, TITLES)) == sorted(name_parts(old, TITLES)), (old, new)
            assert names_match(old, new, TITLES), (old, new)


# ---- field order (D7), written out again here and not imported from framings.order
def expected_order(original, framing):
    ids = {kind: [i["id"] for i in original if i["kind"] == kind]
           for kind in ("customer_field", "watchlist_field", "snippet")}
    if framing == 1:
        return [i["id"] for i in original]
    if framing == 2:
        return ids["watchlist_field"] + ids["customer_field"] + ids["snippet"]
    return ids["snippet"] + ids["customer_field"][::-1] + ids["watchlist_field"][::-1]


def check_order(original, framed, framing):
    assert [i["id"] for i in framed] == expected_order(original, framing)


# ---- snippets: each world note is one original, and framings 2 and 3 show that original's alternates
def check_snippets(original, by_framing, wording):
    """`by_framing` is {1: items, 2: items, 3: items} for one alert. Returns the originals found, in order."""
    customer, listed = own_names(original)
    texts = {f: notes(items) for f, items in by_framing.items()}
    found = []
    for item in original:
        if item["kind"] != "snippet":
            continue
        which = which_original(item["value"], customer, listed)     # raises unless one original or an injected text
        found.append(which)
        seen = [texts[f][item["id"]] for f in FRAMINGS]
        if which is None:
            assert item["value"] in INJECTED and seen == [item["value"]] * 3, seen
            continue
        assert seen[0] == item["value"] and len(set(seen)) == 3, seen
        for framing in (2, 3):
            c, w = own_names(by_framing[framing])
            assert seen[framing - 1] == wording[which][framing].format(c=c, w=w), seen
        assert all(len(text.split()) < 25 for text in seen), seen
    return found


# ---- D10: what differs across the three framings of one bundle
def differences(by_framing):
    """Which of order, name format and wording differ pairwise across the three framings of one bundle."""
    def all_differ(values):
        return values[0] != values[1] != values[2] != values[0]

    return {"order": all_differ([[i["id"] for i in by_framing[f]] for f in FRAMINGS]),
            "names": all_differ([own_names(by_framing[f]) for f in FRAMINGS]),
            "wording": all_differ([notes(by_framing[f]) for f in FRAMINGS]),
            "has_note": bool(notes(by_framing[1]))}


# ---- the text-only adjudicator of T02
def text_label(items):
    return label_from_text(items, AS_OF, TITLES)


def check_same_label(by_framing):
    labels = [text_label(by_framing[f]) for f in FRAMINGS]
    assert labels == [labels[0]] * 3, labels


# ---- the wording table itself: one check per rule, each over all 25 rows
def rows(wording):
    """(key, original, key words, alternate) for each of the 50 alternates."""
    return [(key, ORIGINALS[key], row[0], line) for key, row in wording.items() for line in row[2:]]


def fingerprint(wording):
    """SHA-256 (hex) of the alternates alone, in one canonical form.

    Canonical form: a JSON array with one entry per row, the rows sorted by (tag, index); each entry is the array
    [tag, index, framing-2 alternate, framing-3 alternate] with the alternates as stored (placeholders unrendered).
    It is serialised with json.dumps(..., ensure_ascii=False, separators=(",", ":")) and encoded as UTF-8. Key
    words and key phrases are not part of it: only a change to an alternate, or to which original it belongs to,
    changes the value.
    """
    entries = [[tag, index, wording[tag, index][2], wording[tag, index][3]] for tag, index in sorted(wording)]
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def occurrences(phrase, text):
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE))


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def has_word(word, text):
    return re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) is not None


def check_shape(wording):
    assert set(wording) == set(ORIGINALS) and len(wording) == 25
    lines = [line for _, _, _, line in rows(wording)]
    assert len(set(lines)) == 50 and not set(lines) & set(ORIGINALS.values())
    for key, row in wording.items():
        facts, phrases = row[0], row[1]
        assert len(row) == 4 and 2 <= len(facts) <= 4 and len(set(facts)) == len(facts), key
        assert all(has_word(fact, ORIGINALS[key]) for fact in facts), (key, facts)     # taken from the original
        assert phrases and len(set(phrases)) == len(phrases), key
        for phrase in phrases:                                       # two words or more, taken from the original
            assert len(re.split(r"[ -]", phrase)) >= 2 and has_word(phrase, ORIGINALS[key]), (key, phrase)
        if has_word(EXEMPT_PHRASE, ORIGINALS[key]):                   # an original that has the phrase must list it
            assert EXEMPT_PHRASE in phrases, key


def check_reviewed(wording):
    """The alternates are byte for byte the set the owner reviewed. An edit needs a fresh review and a new pin."""
    assert fingerprint(wording) == REVIEWED_FINGERPRINT


def check_phrases(wording):
    for key, row in wording.items():
        for line in row[2:]:
            assert [phrase for phrase in row[1] if not has_word(phrase, line)] == [], (key, line)


def check_close_associate_count(wording):
    """"close associate" appears exactly as often as in the original: never dropped, never added."""
    for key, original, _, line in rows(wording):
        assert occurrences(EXEMPT_PHRASE, line) == occurrences(EXEMPT_PHRASE, original), (key, line)


def check_facts(wording):
    for key, _, facts, line in rows(wording):
        assert [fact for fact in facts if not has_word(fact, line)] == [], (key, line)


def check_placeholders(wording):
    for key, original, _, line in rows(wording):
        assert placeholders(line) == placeholders(original), (key, line)


def check_length(wording):
    for key, _, _, line in rows(wording):
        assert len(line.format(c=C, w=W).split()) < 25, (key, line)


def check_no_instruction(wording):
    for key, _, _, line in rows(wording):
        text = line.lower().replace(EXEMPT_PHRASE, "")
        assert [word for word in INSTRUCTION_WORDS if word in text] == [], (key, line)


def check_polarity(wording):
    for key, original, _, line in rows(wording):
        assert bool(NEGATION.search(line)) == bool(NEGATION.search(original)), (key, line)


def check_predicates(wording):
    """The T02 adjudicator's own keyword predicates read each alternate as its note type and as no other."""
    for (tag, index), _, _, line in rows(wording):
        text = line.format(c=C, w=W)
        assert says_same_person(text, C, W) == (tag == "identity_link"), text
        assert says_continuing_risk(text) == (tag == "continuing_risk"), text
        assert says_relationship(text) == (tag == "relationship"), text
        if tag == "continuing_risk":                                 # rubric: still ... after leaving office
            assert "office" in text, text
        if tag == "relationship":                                    # rubric: the official holds office now
            assert says_current_office(text) and "former" not in text.lower(), text
        if tag == "neutral":
            assert not says_current_office(text), text


WORDING_CHECKS = (check_reviewed, check_shape, check_facts, check_phrases, check_close_associate_count,
                  check_placeholders, check_length, check_no_instruction, check_polarity, check_predicates)


def check_wording(wording):
    for check in WORDING_CHECKS:
        check(wording)
