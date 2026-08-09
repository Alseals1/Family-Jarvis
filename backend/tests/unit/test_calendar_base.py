"""
Unit tests for CalendarProvider abstraction and CalendarEvent dataclass.

Task 1 — feat/calendar-provider-base
All 5 tests must pass without any external dependencies.
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.providers.calendar.base import CalendarEvent, CalendarProvider
from app.models.calendar import CalendarEventResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TZ_UTC = timezone.utc
_TZ_PLUS5 = timezone(timedelta(hours=5))


def _make_event(**overrides) -> CalendarEvent:
    """Return a valid CalendarEvent, applying any overrides."""
    defaults = dict(
        external_id="evt-001",
        calendar_id="cal-001",
        family_id="fam-001",
        family_member_id="mem-001",
        title="Team Standup",
        description=None,
        start_time=datetime(2026, 8, 10, 9, 0, tzinfo=_TZ_UTC),
        end_time=datetime(2026, 8, 10, 9, 30, tzinfo=_TZ_UTC),
        all_day=False,
        location=None,
        recurrence_rule=None,
        status="confirmed",
        source="google",
        raw_data=None,
    )
    defaults.update(overrides)
    return CalendarEvent(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_calendar_event_instantiation():
    """CalendarEvent with all required fields and tz-aware datetimes succeeds."""
    event = _make_event()
    assert event.external_id == "evt-001"
    assert event.family_id == "fam-001"
    assert event.status == "confirmed"
    assert event.start_time.tzinfo is not None
    assert event.end_time.tzinfo is not None


def test_timezone_naive_start_raises():
    """CalendarEvent raises ValueError when start_time is timezone-naive."""
    naive_dt = datetime(2026, 8, 10, 9, 0)   # no tzinfo
    with pytest.raises(ValueError, match="start_time"):
        _make_event(start_time=naive_dt)


def test_calendar_provider_is_abstract():
    """CalendarProvider cannot be instantiated directly — it is an ABC."""
    with pytest.raises(TypeError):
        CalendarProvider()  # type: ignore[abstract]


def test_invalid_status_raises():
    """CalendarEvent rejects status values outside the allowed set."""
    with pytest.raises(ValueError, match="status"):
        _make_event(status="pending")

    with pytest.raises(ValueError, match="status"):
        _make_event(status="")

    # Valid statuses must not raise
    for valid in ("confirmed", "tentative", "cancelled"):
        event = _make_event(status=valid)
        assert event.status == valid


def test_calendar_event_response_excludes_raw_data():
    """
    CalendarEventResponse serializes to a dict that contains no 'raw_data' key.
    raw_data is internal provider payload and must never be returned to clients.
    """
    response = CalendarEventResponse(
        external_id="evt-002",
        calendar_id="cal-001",
        family_id="fam-001",
        family_member_id="mem-001",
        title="Doctor Appointment",
        description="Annual checkup",
        start_time=datetime(2026, 8, 12, 10, 0, tzinfo=_TZ_UTC),
        end_time=datetime(2026, 8, 12, 11, 0, tzinfo=_TZ_UTC),
        all_day=False,
        location="123 Main St",
        recurrence_rule=None,
        status="confirmed",
        source="google",
    )

    serialized = response.model_dump()
    assert "raw_data" not in serialized
    # Confirm expected fields are present
    assert serialized["external_id"] == "evt-002"
    assert serialized["title"] == "Doctor Appointment"
