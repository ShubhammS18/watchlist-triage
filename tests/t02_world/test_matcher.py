"""Tests for worldgen.textutil and worldgen.matcher. Names in these tests are invented examples."""
import pytest

from worldgen.matcher import entry_matches, load_titles, match_all, names_match, parts_match
from worldgen.rng import Stream
from worldgen.textutil import edit_distance, name_parts, within_one_edit

TITLES = load_titles()


@pytest.mark.parametrize("a,b,expected", [
    ("kitten", "sitting", 3), ("flaw", "lawn", 2), ("", "abc", 3), ("abc", "", 3),
    ("abc", "abc", 0), ("abc", "abd", 1), ("abc", "abcd", 1), ("abcd", "abc", 1), ("ab", "ba", 2),
])
def test_edit_distance_known_values(a, b, expected):
    assert edit_distance(a, b) == expected


def test_within_one_edit_agrees_with_edit_distance_on_a_deterministic_sample():
    s = Stream(1, "sample")

    def word():
        return "".join(s.choice("abc") for _ in range(s.randint(0, 5)))

    for _ in range(3000):
        a, b = word(), word()
        assert within_one_edit(a, b) == (edit_distance(a, b) <= 1), (a, b)


def test_name_parts_normalises():
    assert name_parts("Dr. Séverin  Dumarek-Ølsen", TITLES) == ("severin", "dumarek", "ølsen")
    assert name_parts("PROF Maralis Vosken", TITLES) == ("maralis", "vosken")
    assert name_parts("", TITLES) == ()
    assert name_parts("Dr Mr", TITLES) == ()


def test_titles_load_lower_case():
    assert {"dr", "mr", "mrs", "ms"} <= TITLES and all(t == t.lower() for t in TITLES)


@pytest.mark.parametrize("a,b", [
    ("Maralis Vosken", "Maralis Vosken"),               # identical
    ("Maralis Vosken", "Marelis Vosken"),               # spelling variant, one edit
    ("Maralis Vosken", "Maralis Voskena"),              # one letter added
    ("Maralis Vosken", "Marelis Vosker"),               # one edit in each part
    ("Maralis Vosken", "Vosken Maralis"),               # word order
    ("Dr. Maralis Vosken", "Maralis Vosken"),           # title on one side
    ("Prof Maralis Vosken", "Mrs Maralis Vosken"),      # different titles
    ("Séverin Dumarek", "Severin Dumarek"),             # diacritics
    ("Žarko Telen", "Zarko Telen"),
    ("Anne-Marie Kolbek", "Anne Marie Kolbek"),         # hyphen versus space
])
def test_names_that_match(a, b):
    assert names_match(a, b, TITLES)
    assert names_match(b, a, TITLES)


@pytest.mark.parametrize("a,b", [
    ("Maralis Vosken", "Marilus Vosken"),               # two edits in one part
    ("Maralis Vosken", "Maralis Vusknen"),              # two edits in the other part
    ("Maralis Vosken", "Maralis Vosken Telek"),         # different number of parts
    ("Maralis", "Maralis Vosken"),
    ("Maralis Vosken", "Zorvan Telek"),                 # unrelated
    ("Maralis Maralis", "Maralis Vosken"),              # a part cannot be used twice
    ("Tolvaren Kesmik", "Tulvaran Kesmik"),             # two letters apart
    ("", ""), ("Dr", "Mr"),                             # nothing left after titles
])
def test_names_that_do_not_match(a, b):
    assert not names_match(a, b, TITLES)
    assert not names_match(b, a, TITLES)


def test_parts_match_directly():
    assert parts_match(("a", "bb"), ("bb", "a"))
    assert not parts_match((), ())
    assert not parts_match(("a",), ("a", "a"))


def test_alias_on_the_watchlist_side_is_compared():
    entry = {"id": "WLE-0001", "name": "Zorvan Telek", "aliases": ["Maralis Vosken"]}
    assert entry_matches("Marelis Vosken", entry, TITLES)       # via the alias, one edit
    assert entry_matches("Telek Zorvan", entry, TITLES)         # via the primary name
    assert not entry_matches("Dulan Preskor", entry, TITLES)
    assert entry_matches("Zorvan Telek", {"id": "WLE-0002", "name": "Zorvan Telek"}, TITLES)  # no aliases key


def test_match_all_returns_sorted_pairs():
    customers = [
        {"id": "CUS-0002", "name": "Marelis Vosken"},
        {"id": "CUS-0001", "name": "Dr Zorvan Telek"},
        {"id": "CUS-0003", "name": "Dulan Preskor"},
    ]
    watchlist = [
        {"id": "WLE-0002", "name": "Zorvan Telek"},
        {"id": "WLE-0001", "name": "Kelmar Dunsik", "aliases": ["Maralis Vosken"]},
    ]
    assert match_all(customers, watchlist, TITLES) == [("CUS-0001", "WLE-0002"), ("CUS-0002", "WLE-0001")]
