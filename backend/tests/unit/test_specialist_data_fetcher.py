"""
Tests for FamilyDataFetcher — the 5 new specialist methods added in Phase 5.

All Supabase calls and calendar DB queries are mocked.
The 15 tests cover:
  get_food_preferences      (4 tests)
  get_recent_meals          (3 tests)
  get_date_history          (3 tests)
  get_family_preferences    (2 tests)
  get_availability_windows  (3 tests)
"""

from __future__ import annotations

import pytest
from datetime import datetime, date, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

UTC = timezone.utc

FAMILY_ID = "fam-reeds"
MEMBER_A = "mem-001"
MEMBER_B = "mem-002"


# ---------------------------------------------------------------------------
# Helper: build a mock Supabase admin client whose chain can be customised
# ---------------------------------------------------------------------------

def _make_admin(rows: list[dict] | None = None) -> MagicMock:
    """
    Return a mock Supabase client whose fluent query chain always ends with
    .execute() returning the given rows.

    The chain handled is:
      .table().select().eq()...execute()

    Because different new methods chain differently (some add .gte(), .order(),
    .limit()), we use MagicMock's default behaviour of returning itself at
    every step and only pin the terminal .execute() call.
    """
    mock = MagicMock()
    result = MagicMock()
    result.data = rows if rows is not None else []

    # Make every method in the chain return the mock itself so arbitrary
    # chaining works, then pin execute() at the terminal position.
    chain = mock.table.return_value
    for method in ("select", "eq", "gte", "order", "limit", "neq", "lt", "gt"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = result

    # Allow nested chaining (select().eq().eq()... etc.)
    return mock


def _make_db() -> MagicMock:
    """Simple anon-client mock (used for get_events_in_range patching)."""
    return MagicMock()


# ---------------------------------------------------------------------------
# 1. get_food_preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_food_preferences_groups_by_type():
    """Rows are correctly bucketed into favorites / dislikes / restrictions / allergies."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"preference_type": "favorites", "value": "Italian", "family_member_id": None},
        {"preference_type": "dislikes", "value": "mushrooms", "family_member_id": None},
        {"preference_type": "restrictions", "value": "gluten-free", "family_member_id": None},
        {"preference_type": "allergies", "value": "peanuts", "family_member_id": None},
    ]
    db_admin = _make_admin(rows)

    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    result = await fetcher.get_food_preferences(FAMILY_ID)

    assert "Italian" in result["favorites"]
    assert "mushrooms" in result["dislikes"]
    assert "gluten-free" in result["restrictions"]
    assert "peanuts" in result["allergies"]


@pytest.mark.asyncio
async def test_get_food_preferences_returns_empty_lists_when_no_data():
    """When the table is empty all four keys are present but empty."""
    from app.agents.data_fetcher import FamilyDataFetcher

    db_admin = _make_admin([])
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    result = await fetcher.get_food_preferences(FAMILY_ID)

    assert result == {
        "favorites": [],
        "dislikes": [],
        "restrictions": [],
        "allergies": [],
    }


@pytest.mark.asyncio
async def test_get_food_preferences_merges_family_wide_and_per_member():
    """Both family-wide (member_id=None) and per-member rows appear in the result."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"preference_type": "favorites", "value": "Asian", "family_member_id": None},
        {"preference_type": "favorites", "value": "tacos", "family_member_id": MEMBER_A},
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    result = await fetcher.get_food_preferences(FAMILY_ID)

    assert "Asian" in result["favorites"]
    assert "tacos" in result["favorites"]


@pytest.mark.asyncio
async def test_get_food_preferences_restrictions_always_included():
    """Restrictions and allergies appear even alongside many other rows."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"preference_type": "favorites", "value": "Italian", "family_member_id": None},
        {"preference_type": "allergies", "value": "peanuts", "family_member_id": None},
        {"preference_type": "restrictions", "value": "dairy-free", "family_member_id": MEMBER_B},
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    result = await fetcher.get_food_preferences(FAMILY_ID)

    assert "peanuts" in result["allergies"]
    assert "dairy-free" in result["restrictions"]
    # Hard-constraint lists are never empty when data exists
    assert len(result["allergies"]) >= 1
    assert len(result["restrictions"]) >= 1


# ---------------------------------------------------------------------------
# 2. get_recent_meals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_recent_meals_returns_meal_memories_only():
    """Only rows with category='meal' are returned (filtering is done in query)."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"content": "chicken stir-fry", "created_at": "2026-08-07T18:00:00+00:00"},
        {"content": "pasta", "created_at": "2026-08-05T18:00:00+00:00"},
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    meals = await fetcher.get_recent_meals(FAMILY_ID)

    assert "chicken stir-fry" in meals
    assert "pasta" in meals


@pytest.mark.asyncio
async def test_get_recent_meals_returns_empty_list_when_no_meals():
    """Returns [] when no meal memories exist."""
    from app.agents.data_fetcher import FamilyDataFetcher

    db_admin = _make_admin([])
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    meals = await fetcher.get_recent_meals(FAMILY_ID)

    assert meals == []


@pytest.mark.asyncio
async def test_get_recent_meals_sorted_most_recent_first():
    """Rows are ordered most-recent-first (ordering enforced by query; method preserves it)."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"content": "salmon", "created_at": "2026-08-08T18:00:00+00:00"},
        {"content": "tacos", "created_at": "2026-08-01T18:00:00+00:00"},
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    meals = await fetcher.get_recent_meals(FAMILY_ID)

    assert meals[0] == "salmon"
    assert meals[1] == "tacos"


# ---------------------------------------------------------------------------
# 3. get_date_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_date_history_returns_sorted_records():
    """Records come back in the order the DB returns them (caller passes order)."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {
            "date": "2026-07-28",
            "activity": "dinner and a movie",
            "restaurant": "Carmine's Italian",
            "notes": "great wine list",
            "rating": 5,
        },
        {
            "date": "2026-06-14",
            "activity": "concert",
            "restaurant": None,
            "notes": None,
            "rating": 4,
        },
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    history = await fetcher.get_date_history(FAMILY_ID)

    assert len(history) == 2
    assert history[0]["date"] == "2026-07-28"
    assert history[0]["activity"] == "dinner and a movie"
    assert history[0]["restaurant"] == "Carmine's Italian"
    assert history[0]["rating"] == 5


@pytest.mark.asyncio
async def test_get_date_history_returns_empty_list_when_none():
    """Returns [] when the date_history table has no rows for this family."""
    from app.agents.data_fetcher import FamilyDataFetcher

    db_admin = _make_admin([])
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    history = await fetcher.get_date_history(FAMILY_ID)

    assert history == []


@pytest.mark.asyncio
async def test_get_date_history_limit_respected():
    """The method passes limit=N to the DB query; result length matches rows returned."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"date": f"2026-0{i}-01", "activity": f"activity-{i}",
         "restaurant": None, "notes": None, "rating": 3}
        for i in range(1, 4)
    ]
    db_admin = _make_admin(rows)

    # Capture .limit() call
    limit_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.data = rows
    limit_mock.execute.return_value = result_mock
    db_admin.table.return_value.select.return_value.eq.return_value.order.return_value.limit = MagicMock(
        return_value=limit_mock
    )

    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    history = await fetcher.get_date_history(FAMILY_ID, limit=3)

    assert len(history) == 3
    # Verify .limit(3) was called on the chain
    db_admin.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# 4. get_family_preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_family_preferences_returns_flat_dict():
    """Rows become a flat key→value dict; family-wide rows use plain key."""
    from app.agents.data_fetcher import FamilyDataFetcher

    rows = [
        {"key": "budget", "value": "medium", "family_member_id": None},
        {"key": "cuisine", "value": "Italian", "family_member_id": None},
        {"key": "budget", "value": "low", "family_member_id": MEMBER_A},
    ]
    db_admin = _make_admin(rows)
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    prefs = await fetcher.get_family_preferences(FAMILY_ID, "dining")

    assert prefs["budget"] == "medium"          # family-wide row
    assert prefs["cuisine"] == "Italian"
    assert prefs[f"{MEMBER_A}.budget"] == "low"  # per-member row namespaced


@pytest.mark.asyncio
async def test_get_family_preferences_empty_category_returns_empty_dict():
    """Returns {} when no rows match family_id + category."""
    from app.agents.data_fetcher import FamilyDataFetcher

    db_admin = _make_admin([])
    fetcher = FamilyDataFetcher(db=_make_db(), db_admin=db_admin)
    prefs = await fetcher.get_family_preferences(FAMILY_ID, "activities")

    assert prefs == {}


# ---------------------------------------------------------------------------
# 5. get_availability_windows
# ---------------------------------------------------------------------------

EVENT_ROW = {
    "external_id": "evt-001",
    "calendar_id": "cal-001",
    "family_id": FAMILY_ID,
    "family_member_id": MEMBER_A,
    "title": "Work standup",
    "description": None,
    "start_time": "2026-08-22T09:00:00+00:00",
    "end_time": "2026-08-22T09:30:00+00:00",
    "all_day": False,
    "location": None,
    "recurrence_rule": None,
    "status": "confirmed",
    "source": "manual",
}


def _make_availability_window():
    """Build a real AvailabilityWindow for use in mocks."""
    from app.models.calendar import AvailabilityWindow

    return AvailabilityWindow(
        member_id="family",
        member_name="family",
        date="2026-08-22",
        start_time=datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 22, 22, 0, tzinfo=UTC),
        duration_minutes=240,
    )


@pytest.mark.asyncio
async def test_get_availability_windows_calls_conflict_logic():
    """get_availability_windows calls get_events_in_range and get_family_availability."""
    from app.agents.data_fetcher import FamilyDataFetcher

    window = _make_availability_window()
    start = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)

    with patch("app.agents.data_fetcher.get_events_in_range", return_value=[EVENT_ROW]) as mock_get, \
         patch("app.agents.data_fetcher.get_family_availability", return_value=[window]) as mock_avail:

        fetcher = FamilyDataFetcher(db=_make_db(), db_admin=_make_admin())
        result = await fetcher.get_availability_windows(FAMILY_ID, start, end)

        mock_get.assert_called_once()
        mock_avail.assert_called_once()

    assert len(result) == 1
    assert result[0]["date"] == "2026-08-22"
    assert result[0]["duration_minutes"] == 240


@pytest.mark.asyncio
async def test_get_availability_windows_respects_min_window_minutes():
    """min_window_minutes is passed through to get_family_availability."""
    from app.agents.data_fetcher import FamilyDataFetcher

    window = _make_availability_window()
    start = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)

    with patch("app.agents.data_fetcher.get_events_in_range", return_value=[EVENT_ROW]), \
         patch("app.agents.data_fetcher.get_family_availability", return_value=[window]) as mock_avail:

        fetcher = FamilyDataFetcher(db=_make_db(), db_admin=_make_admin())
        await fetcher.get_availability_windows(FAMILY_ID, start, end, min_window_minutes=120)

        _, kwargs = mock_avail.call_args
        assert kwargs.get("min_window_minutes") == 120 or mock_avail.call_args[0][3] == 120 or \
               mock_avail.call_args.kwargs.get("min_window_minutes") == 120 or \
               any(a == 120 for a in mock_avail.call_args.args)


@pytest.mark.asyncio
async def test_get_availability_windows_returns_empty_when_no_free_time():
    """Returns [] when get_family_availability finds no shared windows."""
    from app.agents.data_fetcher import FamilyDataFetcher

    start = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)

    with patch("app.agents.data_fetcher.get_events_in_range", return_value=[EVENT_ROW]), \
         patch("app.agents.data_fetcher.get_family_availability", return_value=[]):

        fetcher = FamilyDataFetcher(db=_make_db(), db_admin=_make_admin())
        result = await fetcher.get_availability_windows(FAMILY_ID, start, end)

    assert result == []
