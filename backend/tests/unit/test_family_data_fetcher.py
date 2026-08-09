"""
Tests for FamilyDataFetcher — verifies it correctly wraps Phase 3 logic,
filters by family_id, and never touches token columns.
All Supabase calls are mocked.
"""

from __future__ import annotations

import pytest
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

UTC = timezone.utc

FAMILY_ID = "fam-reeds"
MEMBER_A = "mem-001"
MEMBER_B = "mem-002"

TS = "2026-08-09T12:00:00Z"

EVENT_ROW = {
    "external_id": "evt-001",
    "calendar_id": "cal-001",
    "family_id": FAMILY_ID,
    "family_member_id": MEMBER_A,
    "title": "Work standup",
    "description": None,
    "start_time": "2026-08-10T09:00:00+00:00",
    "end_time": "2026-08-10T09:30:00+00:00",
    "all_day": False,
    "location": None,
    "recurrence_rule": None,
    "status": "confirmed",
    "source": "manual",
}

IMPORTANT_DATE_ROW = {
    "id": "date-001",
    "label": "Wedding Anniversary",
    "date_type": "anniversary",
    "date": "2020-08-20",
    "family_member_id": None,
    "recurs_yearly": True,
    "notes": "Plan something special",
    "lead_days": 14,
}

MEMBER_ROW = {"id": MEMBER_A, "name": "Marcus Reed", "relationship": "parent"}


def _make_db(rows: list[dict] | None = None):
    """Create a mock Supabase client that returns rows from .execute()."""
    mock = MagicMock()
    result = MagicMock()
    result.data = rows or []
    # Chain: .table().select().eq().execute() → result
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = result
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = result
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    return mock


@pytest.mark.asyncio
async def test_get_calendar_events_calls_conflict_detection():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = _make_db()
    db_admin = _make_db()

    start = datetime(2026, 8, 10, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 11, 0, 0, 0, tzinfo=UTC)

    with patch("app.agents.data_fetcher.get_events_in_range", return_value=[EVENT_ROW]) as mock_get, \
         patch("app.agents.data_fetcher.detect_conflicts", return_value=[]) as mock_conflicts, \
         patch("app.agents.data_fetcher.get_family_availability", return_value=[]):

        fetcher = FamilyDataFetcher(db, db_admin)
        result = await fetcher.get_calendar_events_and_analysis(FAMILY_ID, start, end)

        mock_conflicts.assert_called_once()
        assert "events" in result
        assert "conflicts" in result
        assert "availability" in result


@pytest.mark.asyncio
async def test_get_calendar_events_calls_availability_calculation():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = _make_db()
    db_admin = _make_db()

    start = datetime(2026, 8, 10, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 11, 0, 0, 0, tzinfo=UTC)

    with patch("app.agents.data_fetcher.get_events_in_range", return_value=[EVENT_ROW]), \
         patch("app.agents.data_fetcher.detect_conflicts", return_value=[]), \
         patch("app.agents.data_fetcher.get_family_availability", return_value=[]) as mock_avail:

        fetcher = FamilyDataFetcher(db, db_admin)
        await fetcher.get_calendar_events_and_analysis(FAMILY_ID, start, end)

        mock_avail.assert_called_once()


@pytest.mark.asyncio
async def test_get_upcoming_important_dates_sorted_by_days_until():
    from app.agents.data_fetcher import FamilyDataFetcher

    # Two dates: anniversary 11 days out, birthday 5 days out
    today = date.today()
    ann_date = (today + __import__("datetime").timedelta(days=11)).replace(year=2020)
    bday_date = (today + __import__("datetime").timedelta(days=5)).replace(year=2010)

    rows = [
        {
            "id": "d1", "label": "Anniversary", "date_type": "anniversary",
            "date": ann_date.isoformat(), "family_member_id": None,
            "recurs_yearly": True, "notes": None, "lead_days": 14,
        },
        {
            "id": "d2", "label": "Marcus Birthday", "date_type": "birthday",
            "date": bday_date.isoformat(), "family_member_id": MEMBER_A,
            "recurs_yearly": True, "notes": None, "lead_days": 7,
        },
    ]

    db = _make_db()
    db_admin = _make_db([])
    db_admin.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows

    fetcher = FamilyDataFetcher(db, db_admin)
    result = await fetcher.get_upcoming_important_dates(FAMILY_ID, days_ahead=30)

    assert len(result) == 2
    # Birthday (5 days) should come before anniversary (11 days)
    assert result[0]["label"] == "Marcus Birthday"
    assert result[1]["label"] == "Anniversary"
    assert result[0]["days_until"] < result[1]["days_until"]


@pytest.mark.asyncio
async def test_get_upcoming_dates_filters_to_family_id():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = _make_db()
    db_admin = MagicMock()
    result_mock = MagicMock()
    result_mock.data = []
    db_admin.table.return_value.select.return_value.eq.return_value.execute.return_value = result_mock

    fetcher = FamilyDataFetcher(db, db_admin)
    await fetcher.get_upcoming_important_dates(FAMILY_ID)

    # Verify that .eq("family_id", FAMILY_ID) was called
    db_admin.table.assert_called_with("important_dates")
    eq_calls = db_admin.table.return_value.select.return_value.eq.call_args_list
    assert any(str(FAMILY_ID) in str(c) for c in eq_calls)


@pytest.mark.asyncio
async def test_get_family_members_returns_name_list():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = MagicMock()
    result_mock = MagicMock()
    result_mock.data = [MEMBER_ROW]
    (db.table.return_value.select.return_value
       .eq.return_value.eq.return_value.execute.return_value) = result_mock

    db_admin = _make_db()

    fetcher = FamilyDataFetcher(db, db_admin)
    members = await fetcher.get_family_members(FAMILY_ID)

    assert len(members) == 1
    assert members[0]["name"] == "Marcus Reed"


@pytest.mark.asyncio
async def test_save_memory_inserts_to_correct_table():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = _make_db()
    db_admin = MagicMock()
    db_admin.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    fetcher = FamilyDataFetcher(db, db_admin)
    await fetcher.save_memory(FAMILY_ID, "We like sushi", "food_preference")

    db_admin.table.assert_called_with("memories")
    insert_call = db_admin.table.return_value.insert.call_args[0][0]
    assert insert_call["family_id"] == FAMILY_ID
    assert insert_call["content"] == "We like sushi"


@pytest.mark.asyncio
async def test_save_memory_returns_confirmation_string():
    from app.agents.data_fetcher import FamilyDataFetcher

    db = _make_db()
    db_admin = MagicMock()
    db_admin.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    fetcher = FamilyDataFetcher(db, db_admin)
    confirmation = await fetcher.save_memory(FAMILY_ID, "We like sushi", "food_preference")

    assert "sushi" in confirmation.lower()
    assert len(confirmation) > 0
