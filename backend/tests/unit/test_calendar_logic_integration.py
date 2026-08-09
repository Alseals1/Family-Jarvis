"""
End-to-end calendar logic integration tests.

Builds CalendarEvent objects directly from fixture data — no DB, no HTTP, no LLM.
Runs them through detect_conflicts and get_availability to validate the full
Phase 3 logic chain using the same event scenarios as the demo seed.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.providers.calendar.base import CalendarEvent
from app.logic.conflicts import detect_conflicts
from app.logic.availability import get_availability, get_family_availability

UTC = ZoneInfo("UTC")

FAMILY_ID = "00000000-0000-0000-0000-000000000001"
MARCUS_ID = "00000000-0000-0000-0001-000000000001"
PRIYA_ID  = "00000000-0000-0000-0001-000000000002"
ELI_ID    = "00000000-0000-0000-0001-000000000003"
ZOE_ID    = "00000000-0000-0000-0001-000000000004"


def _evt(
    eid: str,
    member_id: str,
    title: str,
    start: datetime,
    end: datetime,
    all_day: bool = False,
    status: str = "confirmed",
) -> CalendarEvent:
    return CalendarEvent(
        external_id=eid,
        calendar_id="cal-seed",
        family_id=FAMILY_ID,
        family_member_id=member_id,
        title=title,
        description=None,
        start_time=start,
        end_time=end,
        all_day=all_day,
        location=None,
        recurrence_rule=None,
        status=status,
        source="manual",
        raw_data=None,
    )


# ── Seed-aligned fixture events (week of 2026-08-09) ────────────────────────

SEED_EVENTS: list[CalendarEvent] = [
    # Monday
    _evt("evt-mon-marcus", MARCUS_ID, "Work standup",
         datetime(2026, 8, 10, 9, 0, tzinfo=UTC), datetime(2026, 8, 10, 9, 30, tzinfo=UTC)),
    _evt("evt-mon-priya", PRIYA_ID, "Client call",
         datetime(2026, 8, 10, 14, 0, tzinfo=UTC), datetime(2026, 8, 10, 15, 0, tzinfo=UTC)),
    # Tuesday
    _evt("evt-tue-eli", ELI_ID, "Soccer practice",
         datetime(2026, 8, 11, 16, 0, tzinfo=UTC), datetime(2026, 8, 11, 17, 30, tzinfo=UTC)),
    _evt("evt-tue-zoe", ZOE_ID, "Dance class",
         datetime(2026, 8, 11, 16, 0, tzinfo=UTC), datetime(2026, 8, 11, 17, 0, tzinfo=UTC)),
    # Wednesday
    _evt("evt-wed-marcus", MARCUS_ID, "Doctor appointment",
         datetime(2026, 8, 12, 10, 0, tzinfo=UTC), datetime(2026, 8, 12, 11, 0, tzinfo=UTC)),
    # Thursday
    _evt("evt-thu-priya", PRIYA_ID, "Work presentation",
         datetime(2026, 8, 13, 13, 0, tzinfo=UTC), datetime(2026, 8, 13, 14, 0, tzinfo=UTC)),
    # Friday — intentionally empty (free evening verified by absence)
    # Saturday — cross-member same time (different people, not a double-booking conflict)
    _evt("evt-sat-marcus", MARCUS_ID, "Soccer",
         datetime(2026, 8, 15, 10, 0, tzinfo=UTC), datetime(2026, 8, 15, 11, 0, tzinfo=UTC)),
    _evt("evt-sat-priya", PRIYA_ID, "Dentist",
         datetime(2026, 8, 15, 10, 0, tzinfo=UTC), datetime(2026, 8, 15, 11, 30, tzinfo=UTC)),
    # Sunday — same-person double-booking (conflict)
    _evt("evt-sun-marcus-a", MARCUS_ID, "Marcus double-booked A",
         datetime(2026, 8, 16, 14, 0, tzinfo=UTC), datetime(2026, 8, 16, 15, 0, tzinfo=UTC)),
    _evt("evt-sun-marcus-b", MARCUS_ID, "Marcus double-booked B",
         datetime(2026, 8, 16, 14, 30, tzinfo=UTC), datetime(2026, 8, 16, 15, 30, tzinfo=UTC)),
]

WEEK_START = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
WEEK_END   = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_marcus_double_booking_sunday_detected():
    """Marcus's two overlapping Sunday events are detected as a conflict."""
    conflicts = detect_conflicts(SEED_EVENTS)
    marcus_conflicts = [c for c in conflicts if c.member_id == MARCUS_ID]
    assert len(marcus_conflicts) == 1
    titles = {marcus_conflicts[0].event_a_title, marcus_conflicts[0].event_b_title}
    assert "Marcus double-booked A" in titles
    assert "Marcus double-booked B" in titles
    assert marcus_conflicts[0].overlap_minutes == 30


def test_saturday_cross_member_no_same_person_conflict():
    """Marcus and Priya both at 10am Saturday is NOT a same-person conflict."""
    conflicts = detect_conflicts(SEED_EVENTS)
    sat_titles = {"Soccer", "Dentist"}
    cross_member_flagged = any(
        {c.event_a_title, c.event_b_title} == sat_titles
        for c in conflicts
    )
    assert not cross_member_flagged


def test_free_friday_evening_identified():
    """No events on Friday → availability windows exist including the evening."""
    friday_start = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
    friday_end   = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    windows = get_availability(SEED_EVENTS, MARCUS_ID, friday_start, friday_end)
    assert len(windows) > 0
    # At least one window covers the evening (after 18:00)
    evening = [w for w in windows if w.end_time.hour >= 20]
    assert len(evening) > 0, "Expected a window reaching into the evening"


def test_week_summary_has_correct_event_count():
    """Seed fixture contains exactly 10 confirmed events."""
    confirmed = [e for e in SEED_EVENTS if e.status == "confirmed"]
    assert len(confirmed) == 10


def test_cancelled_event_excluded_from_conflicts():
    """A cancelled event added to the fixture never appears in conflict results."""
    cancelled = _evt(
        "evt-cancelled", MARCUS_ID, "Cancelled meeting",
        datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
        status="cancelled",
    )
    events = SEED_EVENTS + [cancelled]
    confirmed = [e for e in events if e.status == "confirmed"]
    assert len(confirmed) == 10  # count unchanged

    conflicts = detect_conflicts(events)
    conflict_titles = {c.event_a_title for c in conflicts} | {c.event_b_title for c in conflicts}
    assert "Cancelled meeting" not in conflict_titles


def test_family_availability_friday_evening():
    """All four Reeds members are free on Friday → family window returned."""
    friday_start = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
    friday_end   = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    member_ids = [MARCUS_ID, PRIYA_ID, ELI_ID, ZOE_ID]
    windows = get_family_availability(
        SEED_EVENTS, member_ids, friday_start, friday_end, min_window_minutes=60
    )
    assert len(windows) > 0


def test_event_normalization_in_seed_consistent():
    """Every seed fixture event has timezone-aware UTC datetimes."""
    for event in SEED_EVENTS:
        assert event.start_time.tzinfo is not None, \
            f"'{event.title}' start_time is tz-naive"
        assert event.end_time.tzinfo is not None, \
            f"'{event.title}' end_time is tz-naive"
