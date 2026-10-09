"""Tests for the invented name-part lists in worldgen/names/."""
import re
from itertools import combinations

import pytest

from worldgen import ROOT, load_names
from worldgen.textutil import edit_distance

GIVEN = load_names("given.txt")
FAMILY = load_names("family.txt")
COMMON_GIVEN = load_names("common_given.txt")
COMMON_FAMILY = load_names("common_family.txt")
TITLES = load_names("titles.txt")
FILES = ["given.txt", "family.txt", "titles.txt", "common_given.txt", "common_family.txt"]


def test_list_sizes():
    assert (len(GIVEN), len(FAMILY)) == (150, 150)
    assert (len(COMMON_GIVEN), len(COMMON_FAMILY)) == (12, 12)
    assert len(TITLES) == 12


@pytest.mark.parametrize("filename", FILES)
def test_files_are_plain_lf_lines(filename):
    text = ROOT.joinpath("names", filename).read_text(encoding="utf-8")
    assert text.endswith("\n") and "\n\n" not in text and "\r" not in text and not text.startswith("\n")


@pytest.mark.parametrize("part", GIVEN + FAMILY, ids=str)
def test_name_parts_are_four_to_nine_latin_letters(part):
    assert re.fullmatch(r"[A-Z][a-z]{3,8}", part), part


@pytest.mark.parametrize("title", TITLES, ids=str)
def test_titles_are_latin_letters(title):
    assert re.fullmatch(r"[A-Z][a-z]{1,5}", title), title


def test_no_duplicates_in_or_between_lists():
    lowered = [p.lower() for p in GIVEN + FAMILY]
    assert len(set(lowered)) == len(lowered)
    assert len({t.lower() for t in TITLES}) == len(TITLES)
    assert not {p.lower() for p in GIVEN + FAMILY} & {t.lower() for t in TITLES}


@pytest.mark.parametrize("name,parts", [("given", GIVEN), ("family", FAMILY)])
def test_parts_in_each_list_are_at_least_three_edits_apart(name, parts):
    close = [(a, b) for a, b in combinations(parts, 2) if edit_distance(a.lower(), b.lower()) < 3]
    assert not close, close


def test_parts_are_three_edits_apart_across_both_lists_too():
    """Stronger than the design note asks: a given and a family part can never be mistaken for each other."""
    close = [(a, b) for a in GIVEN for b in FAMILY if edit_distance(a.lower(), b.lower()) < 3]
    assert not close, close


def test_common_lists_are_subsets():
    assert COMMON_GIVEN and set(COMMON_GIVEN) <= set(GIVEN)
    assert COMMON_FAMILY and set(COMMON_FAMILY) <= set(FAMILY)
    assert len(set(COMMON_GIVEN)) == len(COMMON_GIVEN) and len(set(COMMON_FAMILY)) == len(COMMON_FAMILY)
