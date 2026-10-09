"""Tests for worldgen.pepdates. Twelve months are counted in calendar months, forward from the leaving date."""
from datetime import date

import pytest

from worldgen import load_config
from worldgen.pepdates import date_from_offset, months_after, within_12_months

AS_OF = date(2026, 9, 30)


@pytest.mark.parametrize("offset,inside", [(0, True), (90, True), (335, True), (364, True), (365, True),
                                           (366, False), (380, False), (1460, False)])
def test_day_offsets_around_the_boundary(offset, inside):
    assert within_12_months(date_from_offset(AS_OF, offset), AS_OF) is inside


def test_inside_when_the_as_of_date_is_on_or_before_the_anniversary_and_beyond_when_later():
    left = date(2025, 9, 30)
    assert months_after(left, 12) == date(2026, 9, 30)
    assert within_12_months(left, date(2026, 9, 29))
    assert within_12_months(left, date(2026, 9, 30))               # the anniversary day itself is inside
    assert not within_12_months(left, date(2026, 10, 1))           # one day later is beyond
    assert not within_12_months(date(2025, 9, 29), AS_OF)


def test_a_leaving_date_after_the_as_of_date_fails_closed():
    with pytest.raises(ValueError):
        within_12_months(date(2026, 10, 1), AS_OF)
    assert within_12_months(AS_OF, AS_OF)          # leaving on the as-of date itself is fine


def test_every_configured_offset_matches_the_rule():
    for offset in load_config()["pep_offset_days"]:
        assert within_12_months(date_from_offset(AS_OF, offset), AS_OF) == (offset <= 365)


def test_leaving_on_29_february_has_its_anniversary_on_28_february():
    left = date(2024, 2, 29)                        # 29 February 2025 does not exist
    assert months_after(left, 12) == date(2025, 2, 28)
    assert within_12_months(left, date(2025, 2, 27))
    assert within_12_months(left, date(2025, 2, 28))                # the anniversary is 28 February
    assert not within_12_months(left, date(2025, 3, 1))


def test_counting_runs_forward_from_the_leaving_date_not_back_from_the_as_of_date():
    """The case where the two directions differ: leaving on 28 February, as-of date 29 February a year later."""
    left = date(2027, 2, 28)
    assert months_after(left, 12) == date(2028, 2, 28)
    assert within_12_months(left, date(2028, 2, 28))
    assert not within_12_months(left, date(2028, 2, 29))           # counting back from the as-of date would say inside
    assert within_12_months(date(2027, 3, 1), date(2028, 2, 29))


def test_months_after_clamps_to_the_month_length_and_crosses_years():
    assert months_after(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert months_after(date(2025, 11, 15), 2) == date(2026, 1, 15)
    assert months_after(date(2026, 9, 30), 0) == date(2026, 9, 30)
    assert months_after(date(2024, 9, 30), 24) == date(2026, 9, 30)


def test_date_from_offset():
    assert date_from_offset(AS_OF, 0) == AS_OF
    assert date_from_offset(AS_OF, 366) == date(2025, 9, 29)
    with pytest.raises(ValueError):
        date_from_offset(AS_OF, -1)
