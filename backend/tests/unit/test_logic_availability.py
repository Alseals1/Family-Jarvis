"""
Unit tests for app.logic.availability — availability calculation.

All fixture events are built from CalendarEvent dataclass directly.
No DB, no HTTP, no LLM.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.providers.calendar.base import CalendarEvent
from app.logic.availability import get_availability, get_family_availability
from app.models.calendar import AvailabilityWindow

UTC = ZoneInfo("UTC")

FAMILY_ID = "fam-reeds"
MARCUS_ID = "member-marcus"
PRIYA_ID = "member-priya"
CAL_ID = "cal-001"

# Reference date range: Monday Aug 10 to Tuesday Aug 11 (exclusive)
MON_START = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
MON_END = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)

# Friday Aug 14 to Saturday Aug 15 (exclusive)
FRI_START = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
FRI_END = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)


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
    day: int = 10,
) -> CalendarEvent:
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


def _allday(external_id: str, member_id: str, day: int = 10) -> CalendarEvent:
    return CalendarEvent(
        external_id=external_id,
        calendar_id=CAL_ID,
        family_id=FAMILY_ID,
        family_member_id=member_id,
        title="All Day",
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


def test_empty_events_entire_day_available():
    """No events → full day from day_start_hour to day_end_hour is free."""
    windows = get_availability([], MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    assert len(windows) == 1
    assert windows[0].start_time == datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    assert windows[0].end_time == datetime(2026, 8, 10, 22, 0, tzinfo=UTC)


def test_event_at_9am_blocks_9am_window():
    """9am-10am event → 8am-9am window and 10am-10pm window returned."""
    events = [_event("e1", MARCUS_ID, 9, 10, title="Standup")]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    start_times = [w.start_time.hour for w in windows]
    end_times = [w.end_time.hour for w in windows]
    assert 8 in start_times   # 8am window exists
    assert 10 in start_times  # 10am window exists
    # 9am must NOT be a window start (it's busy)
    assert 9 not in start_times


def test_all_day_event_blocks_full_day():
    """All-day event → no availability windows for that day."""
    events = [_allday("e1", MARCUS_ID, day=10)]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    assert windows == []


def test_cancelled_events_do_not_block():
    """Cancelled events are ignored — full day should be available."""
    events = [_event("e1", MARCUS_ID, 9, 11, status="cancelled", title="Cancelled")]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    # Should have one big window (8am-10pm)
    assert len(windows) == 1
    assert windows[0].start_time.hour == 8
    assert windows[0].end_time.hour == 22


def test_window_shorter_than_minimum_excluded():
    """A 20-minute gap with min=30 → not returned."""
    # Events: 8am-9:50am and 10:10am-10pm — leaves 20 min gap 9:50-10:10
    events = [
        _event("e1", MARCUS_ID, 8, 9, end_minute=50, title="A"),
        _event("e2", MARCUS_ID, 10, 22, start_minute=10, title="B"),
    ]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                min_window_minutes=30,
                                day_start_hour=8, day_end_hour=22)
    # The 20-minute gap should be excluded
    for w in windows:
        assert w.duration_minutes >= 30


def test_free_friday_evening():
    """
    Seed scenario: no events on Friday after 18:00.
    A 6pm-10pm window (240 minutes) should be returned.
    """
    # Events earlier in the day
    events = [
        _event("e1", MARCUS_ID, 9, 10, day=14, title="Morning Meeting"),
        _event("e2", MARCUS_ID, 14, 15, day=14, title="Afternoon Call"),
    ]
    windows = get_availability(events, MARCUS_ID, FRI_START, FRI_END,
                                day_start_hour=8, day_end_hour=22)
    # Should have a window starting at or after 15:00 that extends to 22:00
    evening_windows = [w for w in windows if w.start_time.hour >= 15]
    assert len(evening_windows) >= 1
    latest_window = max(evening_windows, key=lambda w: w.start_time)
    assert latest_window.end_time.hour == 22


def test_family_availability_intersection():
    """
    member A free 18:00-20:00, member B free 17:00-19:00 →
    intersection is 18:00-19:00 (60 minutes).
    """
    # Marcus: event 8am-6pm → free 6pm-10pm
    marcus_events = [_event("m1", MARCUS_ID, 8, 18, day=14, title="Work")]
    # Priya: event 8am-5pm and event 7pm-10pm → free 5pm-7pm
    priya_events = [
        _event("p1", PRIYA_ID, 8, 17, day=14, title="Work"),
        _event("p2", PRIYA_ID, 19, 22, day=14, title="Evening Plans"),
    ]
    all_events = marcus_events + priya_events

    windows = get_family_availability(
        all_events,
        [MARCUS_ID, PRIYA_ID],
        FRI_START, FRI_END,
        min_window_minutes=30,
    )
    # Should find a window in the 6pm-7pm overlap
    assert len(windows) >= 1
    for w in windows:
        assert w.duration_minutes >= 30


def test_family_availability_no_intersection():
    """Members never free at the same time → empty result."""
    # Marcus free 8am-12pm, Priya free 12pm-10pm (they don't overlap — touching)
    marcus_events = [_event("m1", MARCUS_ID, 12, 22, day=14, title="Busy afternoon")]
    priya_events  = [_event("p1", PRIYA_ID,  8, 12, day=14, title="Busy morning")]
    all_events = marcus_events + priya_events

    windows = get_family_availability(
        all_events,
        [MARCUS_ID, PRIYA_ID],
        FRI_START, FRI_END,
        min_window_minutes=60,
    )
    assert windows == []


def test_day_boundary_respected():
    """Events outside day_start/day_end hours are ignored for windowing."""
    # Event at 6am (before day_start=8) — should not affect availability at 8am
    events = [_event("e1", MARCUS_ID, 6, 7, day=10, title="Early Meeting")]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    # Full 8am-10pm window should still be available
    assert len(windows) == 1
    assert windows[0].start_time.hour == 8
    assert windows[0].end_time.hour == 22


def test_back_to_back_events_no_gap():
    """Events from 9am-12pm and 12pm-3pm → no window between them."""
    events = [
        _event("e1", MARCUS_ID, 9, 12, title="Morning Block"),
        _event("e2", MARCUS_ID, 12, 15, title="Afternoon Block"),
    ]
    windows = get_availability(events, MARCUS_ID, MON_START, MON_END,
                                day_start_hour=8, day_end_hour=22)
    # Windows: 8am-9am, 3pm-10pm — no 12pm-12pm window
    start_times = [w.start_time.hour for w in windows]
    assert 12 not in start_times   # No noon window
    # Should still have early and late windows
    assert any(w.start_time.hour == 8 for w in windows)
    assert any(w.start_time.hour == 15 for w in windows)
