"""Structure checks for docs/rubric.md (task T01-rubric; requirements FR-5, AC-17).

These tests check structure, not correctness of the rules. They only prove that
the required sections, labels with their actions, the Article 22 citation, the
provenance fields and the world-mix numbers are present. Whether the rules are
right is a matter for the owner's and the independent reviewer's reading.
"""
import re
from pathlib import Path

import pytest

RUBRIC = Path(__file__).resolve().parents[2] / "docs" / "rubric.md"

SECTIONS = [
    "Scope",
    "Identifiers",
    "Core principle",
    "What evidence is sufficient to close",
    "Labels",
    "PEP status and dates",
    "Relatives and close associates",
    "Contradictory evidence",
    "Snippets",
    "The five families",
    "Supporting evidence key",
    "Provenance",
    "World mix",
    "Changelog",
]
LABEL_ACTIONS = {
    "TRUE_MATCH": "ESCALATE",
    "AMBIGUOUS_BY_DESIGN": "ESCALATE",
    "CLEAR_FALSE_POSITIVE": "CLOSE",
}


@pytest.fixture(scope="module")
def text():
    assert RUBRIC.is_file(), f"missing {RUBRIC}"
    return RUBRIC.read_text(encoding="utf-8")


def section(text, title, level):
    """Body of the heading `title` up to the next heading of the same or higher level."""
    pattern = rf"^{'#' * level} {re.escape(title)}\n(.*?)(?=^#{{1,{level}}} |\Z)"
    match = re.search(pattern, text, re.S | re.M)
    assert match, f"missing section: {title}"
    return match.group(1)


def test_version_line(text):
    assert re.search(r"^# Synthetic-world adjudication rubric, version 1\.2$", text, re.M)


@pytest.mark.parametrize("title", SECTIONS)
def test_required_section_present(text, title):
    assert section(text, title, 2).strip()


@pytest.mark.parametrize("label,action", LABEL_ACTIONS.items())
def test_label_has_its_correct_action(text, label, action):
    body = section(text, label, 3)
    assert body.count("Correct action:") == 1
    assert f"Correct action: {action}" in body


def test_article_22_citation(text):
    body = section(text, "PEP status and dates", 2)
    for needle in ("Directive (EU) 2015/849", "Article 22", "legislation.gov.uk/eudr/2015/849/article/22"):
        assert needle in body


@pytest.mark.parametrize("field", ["id", "as_of_date", "source", "version"])
def test_provenance_field_listed(text, field):
    assert f"`{field}`" in section(text, "Provenance", 2)


def test_world_mix_numbers(text):
    body = section(text, "World mix", 2)
    for needle in (
        "600 alerts",
        "30 TRUE_MATCH",
        "6 per primary family",
        "30 AMBIGUOUS_BY_DESIGN",
        "540 CLEAR_FALSE_POSITIVE",
        "outside the 600",
    ):
        assert needle in body
