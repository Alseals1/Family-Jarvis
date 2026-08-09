"""
Date math utilities for Family JARVIS.

All functions are pure Python — no LLM, no DB, no HTTP.
These are the primitive operations used by conflict detection,
availability calculation, and the proactive intelligence layer.

Uses zoneinfo (stdlib, Python 3.9+) — NOT pytz.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def intervals_overlap(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    """
    Return True if the two half-open intervals [start_a, end_a) and
    [start_b, end_b) overlap.

    Both intervals must be timezone-aware.
    Raises ValueError if start > end for either interval.
    """
    if start_a > end_a:
        raise ValueError(
            f"Interval A is invalid: start_a ({start_a}) > end_a ({end_a})"
        )
    if start_b > end_b:
        raise ValueError(
            f"Interval B is invalid: start_b ({start_b}) > end_b ({end_b})"
        )
    # Half-open intervals [a, b) and [c, d) overlap iff a < d and c < b
    return start_a < end_b and start_b < end_a


def parse_date_range(start_str: str, end_str: str) -> tuple[datetime, datetime]:
    """
    Parse YYYY-MM-DD strings and return tz-aware datetimes at midnight UTC.

    Raises ValueError on bad input — never silently coerces.
    """
    utc = ZoneInfo("UTC")
    try:
        start_date = date.fromisoformat(start_str)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid start date {start_str!r}: {exc}") from exc
    try:
        end_date = date.fromisoformat(end_str)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid end date {end_str!r}: {exc}") from exc

    start_dt = datetime(
        start_date.year, start_date.month, start_date.day, tzinfo=utc
    )
    end_dt = datetime(end_date.year, end_date.month, end_date.day, tzinfo=utc)
    return start_dt, end_dt


def next_occurrence(event_date: date, reference: date) -> date:
    """
    Return the next occurrence of a yearly-recurring date on or after reference.

    Example: anniversary May 15, reference Aug 9 → May 15 next year
    Example: anniversary Sep 1, reference Aug 9 → Sep 1 this year
    """
    candidate = event_date.replace(year=reference.year)
    if candidate >= reference:
        return candidate
    # Try next year — handle Feb 29 edge case
    try:
        return candidate.replace(year=reference.year + 1)
    except ValueError:
        # Feb 29 on a non-leap next year → use Mar 1
        return date(reference.year + 1, 3, 1)


def days_until(target: date, from_date: date) -> int:
    """
    Return signed number of days from from_date to target.

    Positive = future, 0 = today, negative = past.
    """
    return (target - from_date).days


def week_start(dt: datetime, timezone_str: str) -> datetime:
    """
    Return Monday 00:00:00 of the week containing dt, in the given timezone.
    """
    tz = ZoneInfo(timezone_str)
    # Convert to local time first
    local_dt = dt.astimezone(tz)
    # Monday is weekday 0
    days_since_monday = local_dt.weekday()
    monday = local_dt - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def week_end(dt: datetime, timezone_str: str) -> datetime:
    """
    Return Sunday 23:59:59 of the week containing dt, in the given timezone.
    """
    tz = ZoneInfo(timezone_str)
    local_dt = dt.astimezone(tz)
    # Sunday is 6 days after Monday
    days_since_monday = local_dt.weekday()
    days_to_sunday = 6 - days_since_monday
    sunday = local_dt + timedelta(days=days_to_sunday)
    return sunday.replace(hour=23, minute=59, second=59, microsecond=0)


def to_family_timezone(dt: datetime, timezone_str: str) -> datetime:
    """
    Convert a UTC (or any tz-aware) datetime to the family's local timezone.
    """
    tz = ZoneInfo(timezone_str)
    return dt.astimezone(tz)
