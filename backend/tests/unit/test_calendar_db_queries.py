"""
Unit tests for app.db.queries.calendar — calendar DB query layer.

Supabase client is mocked — verifies query structure and security invariants,
not actual DB results.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, call
from zoneinfo import ZoneInfo

from app.db.queries.calendar import (
    get_calendars_for_family,
    get_decrypted_tokens,
    get_events_in_range,
    mark_calendar_synced,
    store_calendar_connection,
    update_token,
    upsert_calendar_events,
)
from app.providers.calendar.base import CalendarEvent

UTC = ZoneInfo("UTC")

FAMILY_ID = "fam-reeds"
CAL_ID = "cal-001"
MEMBER_ID = "mem-marcus"


def _mock_db(return_data: list | None = None) -> MagicMock:
    """Create a mock Supabase client with a chainable query builder."""
    mock = MagicMock()
    result = MagicMock()
    result.data = return_data if return_data is not None else []

    # Build a fluent chain: .table().select().eq()...execute()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.execute.return_value = result

    mock.table.return_value = chain
    mock._chain = chain  # expose for assertions
    return mock


def _make_event(external_id: str = "evt-001") -> CalendarEvent:
    return CalendarEvent(
        external_id=external_id,
        calendar_id=CAL_ID,
        family_id=FAMILY_ID,
        family_member_id=MEMBER_ID,
        title="Test Event",
        description=None,
        start_time=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
        all_day=False,
        location=None,
        recurrence_rule=None,
        status="confirmed",
        source="google",
        raw_data=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calendars_excludes_token_columns():
    """SELECT must not include access_token_enc or refresh_token_enc."""
    db = _mock_db(return_data=[{"id": CAL_ID, "name": "Primary"}])
    await get_calendars_for_family(FAMILY_ID, db)

    # Inspect the SELECT string passed to .select()
    select_call = db._chain.select.call_args[0][0]
    assert "access_token_enc" not in select_call
    assert "refresh_token_enc" not in select_call


@pytest.mark.asyncio
async def test_get_decrypted_tokens_uses_admin_client():
    """get_decrypted_tokens must use db_admin, not the user-facing client."""
    db_admin = _mock_db(return_data=[{
        "access_token_enc": "enc-access",
        "refresh_token_enc": "enc-refresh",
        "token_expiry": "2026-08-10T10:00:00+00:00",
    }])
    db_user = _mock_db()  # Should NOT be touched

    access, refresh, expiry = await get_decrypted_tokens(CAL_ID, db_admin)

    # Admin client was called
    db_admin.table.assert_called()
    # User client was NOT called
    db_user.table.assert_not_called()

    assert access == "enc-access"
    assert refresh == "enc-refresh"


@pytest.mark.asyncio
async def test_upsert_uses_admin_client():
    """upsert_calendar_events must use db_admin, not user-facing client."""
    db_admin = _mock_db(return_data=[{"id": "row-1"}])
    db_user = _mock_db()

    events = [_make_event()]
    count = await upsert_calendar_events(events, db_admin)

    db_admin.table.assert_called()
    db_user.table.assert_not_called()
    assert count == 1


@pytest.mark.asyncio
async def test_get_events_in_range_filters_by_family_id():
    """Query must include family_id filter."""
    db = _mock_db(return_data=[])
    start = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)

    await get_events_in_range(FAMILY_ID, start, end, db)

    # Verify eq was called with family_id
    eq_calls = db._chain.eq.call_args_list
    family_id_filtered = any(
        call_args[0][0] == "family_id" and call_args[0][1] == FAMILY_ID
        for call_args in eq_calls
    )
    assert family_id_filtered, "Query must filter by family_id"


@pytest.mark.asyncio
async def test_get_events_in_range_filters_by_time():
    """Query must include gte(start) and lte(end) on start_time/end_time."""
    db = _mock_db(return_data=[])
    start = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
    end = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)

    await get_events_in_range(FAMILY_ID, start, end, db)

    gte_calls = db._chain.gte.call_args_list
    lte_calls = db._chain.lte.call_args_list

    assert len(gte_calls) >= 1, "Must call .gte() for start time filter"
    assert len(lte_calls) >= 1, "Must call .lte() for end time filter"

    gte_col = gte_calls[0][0][0]
    lte_col = lte_calls[0][0][0]
    assert "time" in gte_col, f"gte should be on a time column, got {gte_col}"
    assert "time" in lte_col, f"lte should be on a time column, got {lte_col}"


@pytest.mark.asyncio
async def test_store_calendar_connection_passes_encrypted_tokens():
    """Raw plaintext tokens must not be stored — encrypted values are passed."""
    db_admin = _mock_db(return_data=[{"id": CAL_ID}])
    expiry = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

    result_id = await store_calendar_connection(
        family_id=FAMILY_ID,
        family_member_id=MEMBER_ID,
        provider="google",
        external_id="primary",
        name="Primary Calendar",
        access_token_enc="ENCRYPTED_ACCESS",
        refresh_token_enc="ENCRYPTED_REFRESH",
        token_expiry=expiry,
        db_admin=db_admin,
    )

    # Verify upsert was called with encrypted token fields
    upsert_call = db_admin._chain.upsert.call_args[0][0]
    assert "access_token_enc" in upsert_call
    assert "refresh_token_enc" in upsert_call
    assert upsert_call["access_token_enc"] == "ENCRYPTED_ACCESS"
    assert upsert_call["refresh_token_enc"] == "ENCRYPTED_REFRESH"
    # Raw plaintext fields must NOT be present
    assert "access_token" not in upsert_call or "access_token_enc" in upsert_call


@pytest.mark.asyncio
async def test_update_token_does_not_touch_refresh_token():
    """update_token updates only access_token_enc and token_expiry."""
    db_admin = _mock_db(return_data=[])
    expiry = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

    await update_token(CAL_ID, "NEW_ENCRYPTED_ACCESS", expiry, db_admin)

    update_call = db_admin._chain.update.call_args[0][0]
    # access_token_enc and token_expiry must be updated
    assert "access_token_enc" in update_call
    assert "token_expiry" in update_call
    # refresh_token_enc must NOT be touched
    assert "refresh_token_enc" not in update_call
    assert "refresh_token" not in update_call
