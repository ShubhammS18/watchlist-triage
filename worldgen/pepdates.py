"""Former-PEP date rules (docs/rubric.md v1.2, "PEP status and dates").

Months are counted as calendar months, forward from the leaving-office date, never in days. A former PEP is
inside 12 months when the as-of date is on or before the 12-month anniversary of the leaving date, and beyond
12 months when the as-of date is later.

29 February: if the anniversary date does not exist, the anniversary is 28 February. So a person who left on
29 February 2024 is inside 12 months up to and including 28 February 2025, and beyond from 1 March 2025.

A leaving date after the as-of date is impossible data, so it raises ValueError (fail closed) instead of being
guessed at.
"""
import calendar
from datetime import date, timedelta


def months_after(d, months):
    """The date `months` calendar months after `d`, with the day clamped to the length of the target month."""
    year, month = divmod(d.year * 12 + (d.month - 1) + months, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def within_12_months(left_office, as_of):
    if left_office > as_of:
        raise ValueError("leaving-office date is after the as-of date")
    return as_of <= months_after(left_office, 12)


def date_from_offset(as_of, days):
    """The calendar date `days` days before the as-of date (0 means the as-of date itself)."""
    if days < 0:
        raise ValueError("offset must not be negative")
    return as_of - timedelta(days=days)
