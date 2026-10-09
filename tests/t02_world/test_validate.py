"""Tests for worldgen.validate and worldgen/schema/world.schema.json."""
import pytest

from worldgen.validate import load_schema, validate

VALID = {"id": "ALT-0001", "as_of_date": "2026-09-30", "source": "worldgen", "version": "1"}
REQUIRED = ["id", "as_of_date", "source", "version"]


def test_schema_requires_the_four_fields():
    assert load_schema()["required"] == REQUIRED


def test_valid_record_is_accepted_and_extra_fields_are_allowed():
    assert validate(VALID) == []
    assert validate({**VALID, "name": "Maralis Vosken", "count": 3}) == []


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_field_is_rejected(field):
    record = {k: v for k, v in VALID.items() if k != field}
    assert validate(record) == [f"missing field: {field}"]


@pytest.mark.parametrize("field,bad", [
    ("id", 5), ("id", "ALT0001"), ("id", "alt-0001"), ("id", "ALT-1"), ("id", ""),
    ("as_of_date", 20260930), ("as_of_date", "2026-02-30"), ("as_of_date", "2026-9-30"),
    ("as_of_date", "20260930"), ("as_of_date", ""),
    ("source", 7), ("source", ""),
    ("version", 1), ("version", ""), ("version", None), ("version", True),
])
def test_wrong_type_or_shape_is_rejected(field, bad):
    problems = validate({**VALID, field: bad})
    assert problems and all(p.startswith(f"{field}:") for p in problems), problems


@pytest.mark.parametrize("record", [[], "text", 3, None])
def test_non_objects_are_rejected(record):
    assert validate(record) == ["record is not an object"]


def test_all_problems_are_reported_together():
    problems = validate({"id": 1, "source": ""})
    assert "missing field: as_of_date" in problems and "missing field: version" in problems
    assert any(p.startswith("id:") for p in problems) and any(p.startswith("source:") for p in problems)


@pytest.mark.parametrize("value,ok", [("", True), ("2025-04-03", True), ("03/04/2025", False), ("current", False), (None, False)])
def test_related_pep_leaving_date_is_empty_or_a_date(value, ok):
    problems = validate({**VALID, "related_pep_left_office_date": value})
    assert (problems == []) is ok, problems


# ---- dates are real calendar dates, and a leaving date is never after the as-of date (review round 2)
DATE_FIELDS = ["date_of_birth", "left_office_date", "related_pep_left_office_date"]


@pytest.mark.parametrize("field", DATE_FIELDS)
@pytest.mark.parametrize("bad", ["2025-02-30", "9999-99-99", "2025-2-03", "03/04/2025", "20250403", " 2025-04-03", 20250403, None])
def test_a_date_field_must_be_a_real_calendar_date(field, bad):
    problems = validate({**VALID, field: bad})
    assert problems and all(p.startswith(f"{field}:") for p in problems), problems
    assert validate({**VALID, field: "2025-04-03"}) == []


def test_only_the_related_pep_leaving_date_may_be_empty():
    assert validate({**VALID, "related_pep_left_office_date": ""}) == []
    assert validate({**VALID, "left_office_date": ""}) == ["left_office_date: not a calendar date written YYYY-MM-DD"]
    assert validate({**VALID, "date_of_birth": ""}) == ["date_of_birth: not a calendar date written YYYY-MM-DD"]


@pytest.mark.parametrize("field", ["left_office_date", "related_pep_left_office_date"])
def test_a_leaving_date_after_the_as_of_date_is_rejected(field):
    assert validate({**VALID, field: "2026-09-30"}) == []                       # on the as-of date itself is allowed
    assert validate({**VALID, field: "2026-10-01"}) == [f"{field}: later than as_of_date"]
    assert validate({**VALID, field: "2031-01-01"}) == [f"{field}: later than as_of_date"]


def test_a_missing_date_field_is_allowed_and_a_missing_as_of_date_is_reported():
    """A missing leaving date means the date is unknown (the rubric then decides); the four required fields stay required."""
    assert validate({**VALID, "relationship_type": "relative", "relationship_to": "a serving minister"}) == []
    assert validate({**VALID, "pep_status": "former"}) == []
    record = {k: v for k, v in VALID.items() if k != "as_of_date"}
    assert validate({**record, "left_office_date": "2031-01-01"}) == ["missing field: as_of_date"]


@pytest.mark.parametrize("field,value,problem", [
    ("date_of_birth", "2025-02-30", "value: not a calendar date written YYYY-MM-DD"),
    ("left_office_date", "9999-99-99", "value: not a calendar date written YYYY-MM-DD"),
    ("left_office_date", "2027-01-01", "value: later than as_of_date"),
    ("related_pep_left_office_date", "2027-01-01", "value: later than as_of_date"),
])
def test_an_evidence_item_showing_a_date_field_is_held_to_the_same_rule(field, value, problem):
    item = {**VALID, "id": "EVD-00001", "kind": "watchlist_field", "field": field, "value": value}
    assert validate(item) == [problem]
    assert validate({**item, "value": "2025-04-03"}) == []
    assert validate({**item, "field": "name", "value": "2027-01-01"}) == []     # not a date field: any text


def test_integer_type_rejects_booleans():
    rule = {"type": "object", "properties": {"n": {"type": "integer"}}}
    assert validate({"n": 3}, rule) == []
    assert validate({"n": True}, rule) == ["n: expected integer"]
