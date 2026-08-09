"""
Unit tests for app.logic.conflicts — conflict detection.

All fixture events are built from CalendarEvent dataclass directly.
No DB, no HTTP, no LLM.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.providers.calendar.base import CalendarEvent
from app.logic.conflicts import detect_conflicts

UTC = ZoneInfo("UTC")

FAMILY_ID = "fam-reeds"
MARCUS_ID = "member-marcus"
PRIYA_ID = "member-priya"
CAL_ID = "cal-001"


def _event(
    external_id: str,
    member_id: str,
    start_hour: int,
    end_hour: int,
    start_minute: int = 0,
    end_minute: int = 0,
    all_day: bool = False,
    status: str = "confirmed",
    title: str = "Event",
    day: int = 9,
) -> CalendarEvent:
    """Helper to create a CalendarEvent fixture."""
    return CalendarEvent(
        external_id=external_id,
        calendar_id=CAL_ID,
        family_id=FAMILY_ID,
        family_member_id=member_id,
        title=title,
        description=None,
        start_time=datetime(2026, 8, day, start_hour, start_minute, tzinfo=UTC),
        end_time=datetime(2026, 8, day, end_hour, end_minute, tzinfo=UTC),
        all_day=all_day,
        location=None,
        recurrence_rule=None,
        status=status,
        source="manual",
        raw_data=None,
    )


def _allday_event(external_id: str, member_id: str, day: int = 9) -> CalendarEvent:
    """Helper for an all-day event."""
    return CalendarEvent(
        external_id=external_id,
        calendar_id=CAL_ID,
        family_id=FAMILY_ID,
        family_member_id=member_id,
        title="All Day Event",
        description=None,
        start_time=datetime(2026, 8, day, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, day + 1, 0, 0, tzinfo=UTC),
        all_day=True,
        location=None,
        recurrence_rule=None,
        status="confirmed",
        source="manual",
        raw_data=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_events_returns_empty():
    assert detect_conflicts([]) == []


def test_non_overlapping_events_no_conflict():
    events = [
        _event("e1", MARCUS_ID, 9, 10, title="Meeting A"),
        _event("e2", MARCUS_ID, 11, 12, title="Meeting B"),
    ]
    assert detect_conflicts(events) == []


def test_adjacent_events_no_conflict():
    # 9am-10am and 10am-11am: touching but not overlapping (half-open intervals)
    events = [
        _event("e1", MARCUS_ID, 9, 10, title="First"),
        _event("e2", MARCUS_ID, 10, 11, title="Second"),
    ]
    assert detect_conflicts(events) == []


def test_overlapping_same_member_is_conflict():
    events = [
        _event("e1", MARCUS_ID, 9, 11, title="Early Meeting"),
        _event("e2", MARCUS_ID, 10, 12, title="Late Meeting"),
    ]
    conflicts = detect_conflicts(events)
    assert len(conflicts) == 1
    assert conflicts[0].member_id == MARCUS_ID
    assert conflicts[0].overlap_minutes == 60


def test_overlapping_different_members_no_conflict():
    # Same time, different members — should NOT be a conflict (different people)
    events = [
        _event("e1", MARCUS_ID, 10, 11, title="Marcus Soccer"),
        _event("e2", PRIYA_ID, 10, 11, title="Priya Dentist"),
    ]
    assert detect_conflicts(events) == []


def test_all_day_does_not_conflict_with_timed_event():
    events = [
        _allday_event("e1", MARCUS_ID),
        _event("e2", MARCUS_ID, 10, 11, title="10am Meeting"),
    ]
    assert detect_conflicts(events) == []


def test_cancelled_events_excluded():
    events = [
        _event("e1", MARCUS_ID, 9, 11, title="Real Meeting"),
        _event("e2", MARCUS_ID, 10, 12, title="Cancelled Meeting", status="cancelled"),
    ]
    # e2 is cancelled → excluded → no conflict
    assert detect_conflicts(events) == []


def test_exact_overlap_at_saturday_10am():
    """
    Reproduce the Reeds demo scenario:
    Marcus has soccer 10am-11am, Priya has dentist 10am-11:30am.
    Different members → NO same-person conflict.
    """
    events = [
        _event("sat-marcus", MARCUS_ID, 10, 11, title="Soccer", day=15),
        _event("sat-priya", PRIYA_ID, 10, 11, end_minute=30, title="Dentist", day=15),
    ]
    # Saturday cross-member scenario: DIFFERENT members → no conflict
    assert detect_conflicts(events) == []


def test_marcus_double_booked():
    """Marcus has two overlapping events Sunday — conflict detected."""
    events = [
        _event("sun1", MARCUS_ID, 14, 15, title="BBQ", day=16),
        _event("sun2", MARCUS_ID, 14, 15, start_minute=30, end_minute=30,
               title="Video Call", day=16),
    ]
    conflicts = detect_conflicts(events)
    assert len(conflicts) == 1
    assert conflicts[0].member_id == MARCUS_ID
    assert conflicts[0].overlap_minutes == 30


def test_conflict_contains_correct_member_name():
    events = [
        _event("e1", MARCUS_ID, 9, 11, title="A"),
        _event("e2", MARCUS_ID, 10, 12, title="B"),
    ]
    conflicts = detect_conflicts(events)
    assert len(conflicts) == 1
    assert conflicts[0].member_id == MARCUS_ID
    assert "A" in (conflicts[0].event_a_title, conflicts[0].event_b_title)
    assert "B" in (conflicts[0].event_a_title, conflicts[0].event_b_title)


def test_deduplication_of_same_external_id():
    """Same event ID appearing twice is treated as one event — no self-conflict."""
    e = _event("dup-id", MARCUS_ID, 9, 11, title="Duplicated Event")
    events = [e, e]  # Same object twice
    assert detect_conflicts(events) == []
