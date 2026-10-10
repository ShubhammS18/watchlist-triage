"""T03: three meaning-preserving framings of every alert and every control twin (FR-21, AC-23)."""
import ast
import hashlib
import json
from collections import Counter

import pytest

import framings
from framing_checks import (ALERTS, BY_ID, EVERY, ORIGINALS, REVIEWED_FINGERPRINT, TITLES, TWINS, WORDING_CHECKS,
                            check_ids, check_names, fingerprint,
                            check_order, check_same_label, check_snippets, check_values, differences, frame_all,
                            own_names, text_label)
from framings import FRAMINGS, frame
from framings.names import format_name
from framings.recognise import INJECTED, which_original
from framings.wording import WORDING
from worldgen import ROOT
from worldgen.snippets import INJECTED_TEXTS, TEMPLATES

WORLD_DIR = ROOT.parent.joinpath("data", "world")
WORLD_HASH = "b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0"
PACKAGE = sorted(ROOT.parent.joinpath("framings").glob("*.py"))


@pytest.fixture(scope="module")
def framed():
    return frame_all()


def per_alert(framed, alert):
    return {f: framed[alert["id"], f] for f in FRAMINGS}


def test_the_whole_world_is_covered(framed):
    assert (len(ALERTS), len(TWINS), len(framed)) == (600, 15, 615 * 3)
    assert len(BY_ID) == 615


# ---- a
def test_evidence_ids_never_change_and_framing_1_is_the_original(framed):
    for (alert_id, framing), items in framed.items():
        check_ids(BY_ID[alert_id]["evidence"], items, framing)


def test_frame_returns_new_dicts_and_leaves_its_input_alone():
    alert = ALERTS[0]
    before = json.dumps(alert, sort_keys=True)
    for framing in FRAMINGS:
        items = frame(alert, framing)
        assert not any(new is old for new in items for old in alert["evidence"])
        items[0]["value"] = "changed"
    assert json.dumps(alert, sort_keys=True) == before


def test_an_unknown_framing_is_refused():
    for bad in (0, 4, "2", None):
        with pytest.raises(ValueError):
            frame(ALERTS[0], bad)


# ---- b
def test_every_value_that_is_not_a_name_or_a_note_is_byte_identical(framed):
    for (alert_id, _), items in framed.items():
        check_values(BY_ID[alert_id]["evidence"], items)


# ---- c
def test_names_and_aliases_keep_their_normalised_parts_and_still_match(framed):
    for (alert_id, _), items in framed.items():
        check_names(BY_ID[alert_id]["evidence"], items)


@pytest.mark.parametrize("written,second,third", [
    ("Dr Drigutek Plukil", "Dr. PLUKIL, Drigutek", "Dr Plukil Drigutek"),              # title without a dot
    ("Dr. Fegivor Vifos", "Dr. VIFOS, Fegivor", "Dr Vifos Fegivor"),                   # title with a dot
    ("Dame. Borâton Vètupen", "Dame. VÈTUPEN, Borâton", "Dame Vètupen Borâton"),       # title, dot and accents
    ("Mrs Nöskun Föbivel", "Mrs. FÖBIVEL, Nöskun", "Mrs Föbivel Nöskun"),
    ("Braskén Drágrituk", "DRÁGRITUK, Braskén", "Drágrituk Braskén"),                  # accents, no title
    ("Kribera Dregrokor", "DREGROKOR, Kribera", "Dregrokor Kribera"),
    ("Bremalen Brehizek", "BREHIZEK, Bremalen", "Brehizek Bremalen"),                  # an alias in the world
    ("Anvar Belo Castrin", "CASTRIN, Anvar Belo", "Castrin Anvar Belo"),               # three tokens, no title
    ("Hon. Anvar Belo Castrin", "Hon. CASTRIN, Anvar Belo", "Hon Castrin Anvar Belo"),
])
def test_name_formats_by_hand(written, second, third):
    assert [format_name(written, f, TITLES) for f in FRAMINGS] == [written, second, third]


def test_a_title_word_is_a_title_only_in_first_place():
    assert format_name("Anvar Lord", 2, TITLES) == "LORD, Anvar"
    assert format_name("Anvar Lord", 3, TITLES) == "Lord Anvar"


@pytest.mark.parametrize("name", ["Castrin", "Dr Castrin", "Dr. Castrin", "", "Anvar  Castrin"])
def test_a_name_that_cannot_be_reordered_is_refused(name):
    for framing in (2, 3):
        with pytest.raises(ValueError):
            format_name(name, framing, TITLES)


def test_capitals_that_would_change_the_letters_are_refused():
    with pytest.raises(ValueError):
        format_name("Tavo Dreß", 2, TITLES)                          # the capital of ß is SS
    assert format_name("Tavo Dreß", 3, TITLES) == "Dreß Tavo"        # framing 3 uses no capitals


def test_the_formats_change_every_name_in_the_world(framed):
    for alert in EVERY:
        for item in alert["evidence"]:
            if item["field"] in framings.NAME_FIELDS:
                assert len({format_name(item["value"], f, TITLES) for f in FRAMINGS}) >= 2, item["value"]
        names = [own_names(framed[alert["id"], f]) for f in FRAMINGS]
        assert names[0] != names[1] != names[2] != names[0], names


# ---- d
def test_field_order_is_the_decided_permutation(framed):
    for (alert_id, framing), items in framed.items():
        check_order(BY_ID[alert_id]["evidence"], items, framing)


def test_the_three_orders_differ_for_every_alert(framed):
    for alert in EVERY:
        assert len({item["kind"] for item in alert["evidence"]}) >= 2            # every alert has two blocks or more
        orders = [tuple(i["id"] for i in framed[alert["id"], f]) for f in FRAMINGS]
        assert len(set(orders)) == 3, alert["id"]


def test_framings_2_and_3_are_grouped_into_blocks(framed):
    def runs(items):
        kinds = [i["kind"] for i in items]
        return [k for n, k in enumerate(kinds) if n == 0 or kinds[n - 1] != k]

    full = {2: ["watchlist_field", "customer_field", "snippet"], 3: ["snippet", "customer_field", "watchlist_field"]}
    for alert in EVERY:
        present = {i["kind"] for i in alert["evidence"]}
        for framing, order in full.items():
            assert runs(framed[alert["id"], framing]) == [k for k in order if k in present]


# ---- e
def test_every_world_note_is_one_original_and_shows_that_originals_alternates(framed):
    seen = Counter()
    for alert in EVERY:
        seen.update(check_snippets(alert["evidence"], per_alert(framed, alert), WORDING))
    assert seen[None] == 15 and sum(seen.values()) == 455                        # 15 injected, none in a twin
    assert {tag for tag, _ in set(seen) - {None}} == set(TEMPLATES)
    print("\nworld notes per original:", {f"{k[0]}/{k[1]}": v for k, v in sorted(seen.items(), key=str) if k})


def test_injected_texts_are_the_five_of_the_generator():
    assert INJECTED == {text for _, text in INJECTED_TEXTS} and len(INJECTED) == 5


def test_recognition_names_the_original_and_refuses_unknown_and_double_matches(monkeypatch):
    for (tag, index), template in ORIGINALS.items():
        assert which_original(template.format(c="Anvar Castrin", w="Belo Castrin"), "Anvar Castrin",
                              "Belo Castrin") == (tag, index)
    for text in INJECTED:
        assert which_original(text, "Anvar Castrin", "Belo Castrin") is None
    with pytest.raises(ValueError):
        which_original("A note nobody wrote.", "Anvar Castrin", "Belo Castrin")
    first = TEMPLATES["neutral"][0]
    monkeypatch.setitem(TEMPLATES, "copy", (first,))
    with pytest.raises(ValueError):
        which_original(first, "Anvar Castrin", "Belo Castrin")


@pytest.mark.parametrize("check", WORDING_CHECKS, ids=lambda check: check.__name__)
def test_the_wording_table(check):
    """The reviewed fingerprint, key words and phrases, placeholders, length, no instruction, polarity and the
    adjudicator's predicates, for all 25 rows."""
    check(WORDING)


def test_the_review_document_shows_the_whole_wording_set():
    text = ROOT.parent.joinpath("docs", "framings", "wording-set.md").read_text(encoding="utf-8")
    shown = list(ORIGINALS.values()) + [line for row in WORDING.values() for line in row[2:]] + sorted(INJECTED)
    assert [line for line in shown if line not in text] == []
    for key, row in WORDING.items():
        assert ", ".join(row[0]) in text and "; ".join(row[1]) in text, key
    assert REVIEWED_FINGERPRINT in text and fingerprint(WORDING) == REVIEWED_FINGERPRINT


# ---- D10: order and name format differ for every bundle; wording differs wherever a note exists
def test_what_differs_across_the_three_framings(framed):
    counts = Counter()
    for alert in EVERY:
        assert len({item["kind"] for item in alert["evidence"]}) >= 2 and len(own_names(alert["evidence"])) == 2
        found = differences(per_alert(framed, alert))
        assert found["order"] and found["names"], alert["id"]
        assert found["wording"] == found["has_note"], alert["id"]
        counts["bundles"] += 1
        counts["order and names differ"] += found["order"] and found["names"]
        counts["with a note"] += found["has_note"]
        counts["with a note, wording differs"] += found["has_note"] and found["wording"]
        counts["no note"] += not found["has_note"]
        counts["no note, order and names differ"] += not found["has_note"] and found["order"] and found["names"]
    print("\nD10 counts:", dict(counts))
    assert counts == {"bundles": 615, "order and names differ": 615, "with a note": 335,
                      "with a note, wording differs": 335, "no note": 280, "no note, order and names differ": 280}


# ---- f
def test_the_text_adjudicator_gives_one_label_across_the_three_framings(framed):
    for alert in EVERY:
        check_same_label(per_alert(framed, alert))
    counts = Counter(text_label(framed[alert["id"], f]) for alert in ALERTS for f in FRAMINGS)
    assert counts == {"TRUE_MATCH": 90, "AMBIGUOUS_BY_DESIGN": 90, "CLEAR_FALSE_POSITIVE": 1620}


# ---- g
def digest(framed):
    return hashlib.sha256(json.dumps(sorted(framed.items()), ensure_ascii=False).encode("utf-8")).hexdigest()


def test_generating_everything_twice_gives_identical_bytes(framed):
    assert digest(frame_all()) == digest(frame_all()) == digest(framed)


# ---- h
def file_hashes():
    return {path.relative_to(WORLD_DIR).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(WORLD_DIR.rglob("*")) if path.is_file()}


def test_the_world_is_byte_identical_before_and_after_and_the_hash_stands():
    before = file_hashes()
    frame_all()
    after = file_hashes()
    assert after == before and len(before) == 11
    manifest = json.loads(WORLD_DIR.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    lines = "".join(f"{path}:{sha}\n" for path, sha in sorted(after.items()) if path != "MANIFEST.json")
    assert manifest["world_hash"] == WORLD_HASH == hashlib.sha256(lines.encode("utf-8")).hexdigest()


# ---- i
def test_there_are_sources_to_check():
    assert {p.name for p in PACKAGE} == {"__init__.py", "names.py", "order.py", "recognise.py", "wording.py"}


@pytest.mark.parametrize("path", PACKAGE, ids=lambda p: p.name)
def test_the_package_never_mentions_the_answer_files(path):
    text = path.read_text(encoding="utf-8").lower()
    assert not [word for word in ("hidden", "truth", "label") if word in text]


@pytest.mark.parametrize("path", PACKAGE, ids=lambda p: p.name)
def test_the_package_is_pure(path):
    """No randomness, clock, environment or file access, and no import outside itself and three worldgen modules."""
    allowed = {"worldgen.matcher", "worldgen.snippets", "worldgen.textutil", "names", "order", "recognise", "wording"}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            raise AssertionError(f"import {node.names[0].name}")
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed, node.module
        if isinstance(node, ast.Name):
            assert node.id not in ("open", "print", "exec", "eval", "__import__"), node.id
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("now", "today", "environ", "getenv", "read_text", "write_text"), node.attr
