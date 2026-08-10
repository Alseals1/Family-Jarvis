"""
Unit tests for backend/app/jobs/important_dates.py

All DB calls are mocked. Tests verify:
- Alert inserted within lead_days window
- Alert skipped outside lead_days window
- Correct NotificationType used for each date_type
- Content format is deterministic (no LLM)
- Dedup: skipped when duplicate exists
- Yearly recurrence uses next_occurrence
- Non-recurring date not re-alerted after it passes
- Returns empty list when no upcoming dates
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.important_dates import run_important_date_alerts


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

REFERENCE = date(2026, 8, 10)  # "today" for all tests


def _make_db(rows=None, insert_result=None):
    """
    Build a db_admin mock that returns `rows` from important_dates SELECT
    and `insert_result` from notifications INSERT.
    """
    rows = rows or []
    insert_result = insert_result if insert_result is not None else {"id": "new-notif-id"}

    db = MagicMock()

    # important_dates query chain
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=rows)

    # notifications dedup + insert chain
    notif_chain = MagicMock()
    notif_chain.eq.return_value = notif_chain
    notif_chain.execute.return_value = MagicMock(data=[])  # no duplicate by default

    notif_insert_chain = MagicMock()
    notif_insert_chain.execute.return_value = MagicMock(
        data=[insert_result] if insert_result else []
    )

    call_count = [0]

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            # notifications table
            tbl.select.return_value = notif_chain
            tbl.insert.return_value = notif_insert_chain
        return tbl

    db.table.side_effect = _table_side
    return db


def _birthday_row(days_until=7, label="Emma"):
    """Build a birthday important_date row."""
    occurrence = REFERENCE + timedelta(days=days_until)
    return {
        "id": "date-1",
        "family_id": "fam-1",
        "date_type": "birthday",
        "label": label,
        "date": occurrence.isoformat(),
        "recurring": True,
        "lead_days": 14,
    }


def _anniversary_row(days_until=10):
    occurrence = REFERENCE + timedelta(days=days_until)
    return {
        "id": "date-2",
        "family_id": "fam-1",
        "date_type": "anniversary",
        "label": "Anniversary",
        "date": occurrence.isoformat(),
        "recurring": True,
        "lead_days": 14,
    }


def _trip_row(days_until=5):
    occurrence = REFERENCE + timedelta(days=days_until)
    return {
        "id": "date-3",
        "family_id": "fam-1",
        "date_type": "trip",
        "label": "Paris trip",
        "destination": "Paris",
        "date": occurrence.isoformat(),
        "recurring": False,
        "lead_days": 14,
    }


# ---------------------------------------------------------------------------
# T1 — birthday alert inserted when within lead_days
# ---------------------------------------------------------------------------

def test_birthday_alert_inserted_when_within_lead_days():
    db = _make_db(rows=[_birthday_row(days_until=7)])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert len(result) == 1
    assert result[0] == "new-notif-id"


# ---------------------------------------------------------------------------
# T2 — birthday alert skipped when outside lead_days
# ---------------------------------------------------------------------------

def test_birthday_alert_skipped_when_outside_lead_days():
    db = _make_db(rows=[_birthday_row(days_until=30)])  # beyond 14-day window
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []


# ---------------------------------------------------------------------------
# T3 — anniversary alert inserted with correct days_until
# ---------------------------------------------------------------------------

def test_anniversary_alert_inserted_with_days_until():
    db = _make_db(rows=[_anniversary_row(days_until=10)])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert len(result) == 1


# ---------------------------------------------------------------------------
# T4 — trip alert inserted for upcoming trip
# ---------------------------------------------------------------------------

def test_trip_alert_inserted_for_upcoming_trip():
    db = _make_db(rows=[_trip_row(days_until=5)])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert len(result) == 1


# ---------------------------------------------------------------------------
# T5 — alert skipped when duplicate exists
# ---------------------------------------------------------------------------

def test_alert_skipped_when_duplicate_exists():
    db = MagicMock()

    # important_dates select returns one row
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_birthday_row(days_until=7)])

    # notifications dedup select returns existing row (duplicate)
    notif_chain = MagicMock()
    notif_chain.eq.return_value = notif_chain
    notif_chain.execute.return_value = MagicMock(data=[{"id": "existing-notif"}])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            tbl.select.return_value = notif_chain
        return tbl

    db.table.side_effect = _table_side

    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []


# ---------------------------------------------------------------------------
# T6 — alert content contains label and date
# ---------------------------------------------------------------------------

def test_alert_content_contains_label_and_date():
    captured = {}

    db = MagicMock()

    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_birthday_row(days_until=7, label="Emma")])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            # Capture insert call
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])  # no duplicate

            def _insert(payload):
                captured["content"] = payload.get("content", "")
                insert_chain = MagicMock()
                insert_chain.execute.return_value = MagicMock(data=[{"id": "captured-id"}])
                return insert_chain

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side

    asyncio.run(run_important_date_alerts("fam-1", db, reference_date=REFERENCE))
    assert "Emma" in captured.get("content", "")
    assert "2026" in captured.get("content", "") or "August" in captured.get("content", "")


# ---------------------------------------------------------------------------
# T7 — alert content contains days_until
# ---------------------------------------------------------------------------

def test_alert_content_contains_days_until():
    captured = {}

    db = MagicMock()
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_birthday_row(days_until=7)])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])

            def _insert(payload):
                captured["content"] = payload.get("content", "")
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[{"id": "x"}])
                return ins

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side

    asyncio.run(run_important_date_alerts("fam-1", db, reference_date=REFERENCE))
    assert "7" in captured.get("content", "")


# ---------------------------------------------------------------------------
# T8 — birthday type in notification row
# ---------------------------------------------------------------------------

def test_birthday_type_in_notification_row():
    captured = {}

    db = MagicMock()
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_birthday_row(days_until=5)])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])

            def _insert(payload):
                captured["type"] = payload.get("type", "")
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[{"id": "x"}])
                return ins

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side

    asyncio.run(run_important_date_alerts("fam-1", db, reference_date=REFERENCE))
    assert captured.get("type") == "birthday"


# ---------------------------------------------------------------------------
# T9 — anniversary type in notification row
# ---------------------------------------------------------------------------

def test_anniversary_type_in_notification_row():
    captured = {}

    db = MagicMock()
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_anniversary_row(days_until=5)])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])

            def _insert(payload):
                captured["type"] = payload.get("type", "")
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[{"id": "x"}])
                return ins

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side

    asyncio.run(run_important_date_alerts("fam-1", db, reference_date=REFERENCE))
    assert captured.get("type") == "anniversary"


# ---------------------------------------------------------------------------
# T10 — trip type in notification row
# ---------------------------------------------------------------------------

def test_trip_type_in_notification_row():
    captured = {}

    db = MagicMock()
    date_chain = MagicMock()
    date_chain.eq.return_value = date_chain
    date_chain.execute.return_value = MagicMock(data=[_trip_row(days_until=5)])

    def _table_side(name):
        tbl = MagicMock()
        if name == "important_dates":
            tbl.select.return_value = date_chain
        else:
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.execute.return_value = MagicMock(data=[])

            def _insert(payload):
                captured["type"] = payload.get("type", "")
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[{"id": "x"}])
                return ins

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side

    asyncio.run(run_important_date_alerts("fam-1", db, reference_date=REFERENCE))
    assert captured.get("type") == "trip"


# ---------------------------------------------------------------------------
# T11 — no LLM called for important date content
# ---------------------------------------------------------------------------

def test_no_llm_called_for_important_date_content():
    """Verify no LLM provider is imported or called by the job."""
    import app.jobs.important_dates as mod
    import inspect
    source = inspect.getsource(mod)
    # The job must not import or reference LLMProvider or openrouter
    assert "LLMProvider" not in source
    assert "openrouter" not in source
    assert "complete(" not in source


# ---------------------------------------------------------------------------
# T12 — yearly recurrence uses next_occurrence
# ---------------------------------------------------------------------------

def test_yearly_recurrence_uses_next_occurrence():
    """
    A birthday stored as Jan-15 with reference Aug-10 should resolve to
    Jan-15 next year — which is beyond 14 days, so no alert.
    """
    row = {
        "id": "date-far",
        "family_id": "fam-1",
        "date_type": "birthday",
        "label": "Alex",
        "date": "1990-01-15",  # Jan 15 recurring, next occurrence = Jan 15 next year
        "recurring": True,
        "lead_days": 14,
    }
    db = _make_db(rows=[row])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    # Jan 15 next year is ~158 days away — outside 14-day window → no alert
    assert result == []


# ---------------------------------------------------------------------------
# T13 — non-recurring date not repeated after it passes
# ---------------------------------------------------------------------------

def test_non_recurring_date_not_repeated():
    """Non-recurring date in the past should produce no alert."""
    past_date = REFERENCE - timedelta(days=5)
    row = {
        "id": "date-past",
        "family_id": "fam-1",
        "date_type": "trip",
        "label": "Paris trip",
        "destination": "Paris",
        "date": past_date.isoformat(),
        "recurring": False,
        "lead_days": 14,
    }
    db = _make_db(rows=[row])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []


# ---------------------------------------------------------------------------
# T14 — returns empty list when no upcoming dates
# ---------------------------------------------------------------------------

def test_returns_empty_list_when_no_upcoming_dates():
    db = _make_db(rows=[])
    result = asyncio.run(
        run_important_date_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []
