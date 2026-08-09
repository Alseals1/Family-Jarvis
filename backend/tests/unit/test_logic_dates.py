"""
Unit tests for app.logic.dates — date math utilities.
All deterministic — no mocking needed.
"""

import pytest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.logic.dates import (
    days_until,
    intervals_overlap,
    next_occurrence,
    parse_date_range,
    to_family_timezone,
    week_end,
    week_start,
)

UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# ---------------------------------------------------------------------------
# next_occurrence
# ---------------------------------------------------------------------------


def test_next_occurrence_anniversary_before_reference_returns_next_year():
    # Anniversary May 15, reference Aug 9 → next occurrence is May 15 next year
    ann = date(2000, 5, 15)
    ref = date(2026, 8, 9)
    result = next_occurrence(ann, ref)
    assert result == date(2027, 5, 15)


def test_next_occurrence_anniversary_after_reference_returns_this_year():
    # Anniversary Sep 1, reference Aug 9 → next occurrence is Sep 1 this year
    ann = date(2000, 9, 1)
    ref = date(2026, 8, 9)
    result = next_occurrence(ann, ref)
    assert result == date(2026, 9, 1)


def test_next_occurrence_same_day_as_reference_returns_today():
    ref = date(2026, 8, 9)
    ann = date(1990, 8, 9)
    result = next_occurrence(ann, ref)
    assert result == ref


def test_next_occurrence_jan_1_reference_dec_31_returns_same_year():
    # Jan 1 anniversary, reference is Dec 31 → already passed, returns next year
    ann = date(2000, 1, 1)
    ref = date(2026, 12, 31)
    result = next_occurrence(ann, ref)
    assert result == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# days_until
# ---------------------------------------------------------------------------


def test_days_until_today_returns_zero():
    today = date(2026, 8, 9)
    assert days_until(today, today) == 0


def test_days_until_yesterday_returns_negative_one():
    from_d = date(2026, 8, 9)
    yesterday = date(2026, 8, 8)
    assert days_until(yesterday, from_d) == -1


def test_days_until_tomorrow_returns_one():
    from_d = date(2026, 8, 9)
    tomorrow = date(2026, 8, 10)
    assert days_until(tomorrow, from_d) == 1


def test_days_until_twelve_days_future():
    from_d = date(2026, 8, 9)
    target = date(2026, 8, 21)
    assert days_until(target, from_d) == 12


# ---------------------------------------------------------------------------
# intervals_overlap
# ---------------------------------------------------------------------------


def _dt(hour: int, minute: int = 0) -> datetime:
    """Helper: UTC datetime on 2026-08-09 at given hour:minute."""
    return datetime(2026, 8, 9, hour, minute, tzinfo=UTC)


def test_intervals_non_overlapping():
    assert not intervals_overlap(_dt(9), _dt(10), _dt(11), _dt(12))


def test_intervals_adjacent_not_overlapping():
    # 9am-10am and 10am-11am — touching but not overlapping (half-open)
    assert not intervals_overlap(_dt(9), _dt(10), _dt(10), _dt(11))


def test_intervals_overlapping_by_one_hour():
    # 9am-11am and 10am-12pm overlap from 10am-11am
    assert intervals_overlap(_dt(9), _dt(11), _dt(10), _dt(12))


def test_intervals_fully_contained():
    # 10am-11am fully inside 9am-12pm
    assert intervals_overlap(_dt(9), _dt(12), _dt(10), _dt(11))


def test_intervals_identical():
    assert intervals_overlap(_dt(9), _dt(10), _dt(9), _dt(10))


def test_intervals_reversed_a_raises_value_error():
    with pytest.raises(ValueError):
        intervals_overlap(_dt(10), _dt(9), _dt(10), _dt(11))


def test_intervals_reversed_b_raises_value_error():
    with pytest.raises(ValueError):
        intervals_overlap(_dt(9), _dt(10), _dt(12), _dt(11))


# ---------------------------------------------------------------------------
# week_start / week_end
# ---------------------------------------------------------------------------


def test_week_start_monday():
    # 2026-08-09 is a Sunday in ET
    # Monday of that week is 2026-08-03
    dt = datetime(2026, 8, 9, 12, 0, tzinfo=ET)
    ws = week_start(dt, "America/New_York")
    assert ws.weekday() == 0  # Monday
    assert ws.hour == 0
    assert ws.minute == 0
    assert ws.second == 0


def test_week_end_sunday():
    dt = datetime(2026, 8, 9, 12, 0, tzinfo=ET)
    we = week_end(dt, "America/New_York")
    assert we.weekday() == 6  # Sunday
    assert we.hour == 23
    assert we.minute == 59
    assert we.second == 59


def test_week_start_and_end_same_week():
    dt = datetime(2026, 8, 12, 10, 0, tzinfo=ET)  # Wednesday
    ws = week_start(dt, "America/New_York")
    we = week_end(dt, "America/New_York")
    # Both should be in same 7-day window
    assert (we - ws).days == 6


# ---------------------------------------------------------------------------
# to_family_timezone
# ---------------------------------------------------------------------------


def test_to_family_timezone_utc_to_chicago():
    # UTC 18:00 = Chicago CDT 13:00 (UTC-5 in summer)
    utc_dt = datetime(2026, 8, 9, 18, 0, tzinfo=UTC)
    chicago_dt = to_family_timezone(utc_dt, "America/Chicago")
    assert chicago_dt.tzinfo is not None
    assert chicago_dt.hour == 13  # CDT is UTC-5


def test_to_family_timezone_preserves_moment():
    utc_dt = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
    ny_dt = to_family_timezone(utc_dt, "America/New_York")
    # Same moment in time
    assert ny_dt.astimezone(ZoneInfo("UTC")) == utc_dt


# ---------------------------------------------------------------------------
# parse_date_range
# ---------------------------------------------------------------------------


def test_parse_date_range_valid():
    start, end = parse_date_range("2026-08-09", "2026-08-16")
    assert start.year == 2026 and start.month == 8 and start.day == 9
    assert end.year == 2026 and end.month == 8 and end.day == 16
    assert start.tzinfo is not None
    assert end.tzinfo is not None


def test_parse_date_range_midnight_utc():
    start, end = parse_date_range("2026-08-09", "2026-08-16")
    assert start.hour == 0 and start.minute == 0
    assert end.hour == 0 and end.minute == 0


def test_parse_date_range_invalid_start_raises():
    with pytest.raises(ValueError):
        parse_date_range("not-a-date", "2026-08-16")


def test_parse_date_range_invalid_end_raises():
    with pytest.raises(ValueError):
        parse_date_range("2026-08-09", "2026-13-01")
