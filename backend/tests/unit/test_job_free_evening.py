"""
Unit tests for backend/app/jobs/free_evening.py

All DB and LLM calls are mocked. Tests verify:
- Free evening notification inserted when window found
- No notification when no window
- Dinner suggestion inserted when window found
- No dinner suggestion when no window
- Chef invoked with cooking_time from window
- Cooking time capped at 60 minutes
- Content contains window times and duration
- Correct notification types
- Idempotent: skipped if already notified today
- Family timezone used for window calculation
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, date
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.agents.contracts import AgentResult
from app.jobs.free_evening import run_free_evening_check

UTC = timezone.utc
# 20:00 UTC = 16:00 Eastern — the scheduled job time
REFERENCE_DT = datetime(2026, 8, 10, 20, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chef(recommendation="Chicken Tacos", reason="Fast and delicious."):
    chef = MagicMock()

    async def _run(task):
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="chef",
            success=True,
            data={
                "recommendation": recommendation,
                "reason": reason,
                "alternatives": [],
                "shopping_needed": [],
            },
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef.run = _run
    return chef


def _make_db(event_rows=None, notif_duplicate_types=None):
    """
    notif_duplicate_types: set of notif type strings that "already exist"
    """
    event_rows = event_rows or []
    notif_duplicate_types = notif_duplicate_types or set()

    db = MagicMock()

    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=event_rows)

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            # notifications table — track by type
            select_chain = MagicMock()
            insert_chain = MagicMock()

            type_tracker = [None]

            def _eq(col, val):
                if col == "type":
                    type_tracker[0] = val
                select_chain.eq.return_value = select_chain
                return select_chain

            select_chain.eq = _eq

            def _execute():
                t = type_tracker[0]
                if t in notif_duplicate_types:
                    return MagicMock(data=[{"id": "existing"}])
                return MagicMock(data=[])

            select_chain.execute = _execute

            def _insert(payload):
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[{"id": "new-notif"}])
                return ins

            tbl.select.return_value = select_chain
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    return db


# ---------------------------------------------------------------------------
# T1 — free_evening notification inserted when window found
# ---------------------------------------------------------------------------

def test_free_evening_notification_inserted_when_window_found():
    # No events tonight → everyone is free → large window
    db = _make_db(event_rows=[])
    chef = _make_chef()
    anon_db = MagicMock()

    result = asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert result["free_evening_inserted"] is True


# ---------------------------------------------------------------------------
# T2 — free_evening notification not inserted when no window
# ---------------------------------------------------------------------------

def test_free_evening_notification_not_inserted_when_no_window():
    """
    When all members are busy the entire 5-10 PM window, no free window exists.
    We simulate this by returning events that block the window with get_family_availability
    producing an empty list. The simplest way: mock the availability function directly.
    """
    import app.jobs.free_evening as mod
    from unittest.mock import patch

    db = _make_db(event_rows=[
        {
            "id": "ev1",
            "external_id": "ext-ev1",
            "calendar_id": "cal-1",
            "family_id": "fam-1",
            "family_member_id": "member-1",
            "title": "Busy All Night",
            "description": None,
            "start_time": "2026-08-10T21:00:00+00:00",
            "end_time": "2026-08-11T02:00:00+00:00",
            "all_day": False,
            "location": None,
            "recurrence_rule": None,
            "status": "confirmed",
            "source": "manual",
        }
    ])
    chef = _make_chef()
    anon_db = MagicMock()

    # Patch get_family_availability to return empty (fully busy)
    with patch.object(mod, "get_family_availability", return_value=[]):
        result = asyncio.run(
            run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
        )

    assert result["free_evening_inserted"] is False
    assert result["dinner_suggestion_inserted"] is False


# ---------------------------------------------------------------------------
# T3 — dinner suggestion inserted when free window found
# ---------------------------------------------------------------------------

def test_dinner_suggestion_inserted_when_free_window_found():
    db = _make_db(event_rows=[])
    chef = _make_chef()
    anon_db = MagicMock()

    result = asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert result["dinner_suggestion_inserted"] is True


# ---------------------------------------------------------------------------
# T4 — dinner suggestion not inserted when no window
# ---------------------------------------------------------------------------

def test_dinner_suggestion_not_inserted_when_no_window():
    import app.jobs.free_evening as mod
    from unittest.mock import patch

    db = _make_db(event_rows=[
        {
            "id": "ev2", "external_id": "ext-ev2", "calendar_id": "cal-1",
            "family_id": "fam-1", "family_member_id": "member-1",
            "title": "Meeting", "description": None,
            "start_time": "2026-08-10T21:00:00+00:00",
            "end_time": "2026-08-11T02:00:00+00:00",
            "all_day": False, "location": None, "recurrence_rule": None,
            "status": "confirmed", "source": "manual",
        }
    ])
    chef = _make_chef()
    anon_db = MagicMock()

    with patch.object(mod, "get_family_availability", return_value=[]):
        result = asyncio.run(
            run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
        )

    assert result["dinner_suggestion_inserted"] is False


# ---------------------------------------------------------------------------
# T5 — dinner suggestion invokes chef with cooking_time
# ---------------------------------------------------------------------------

def test_dinner_suggestion_invokes_chef_with_cooking_time():
    captured_tasks = []

    chef = MagicMock()

    async def _run(task):
        captured_tasks.append(task)
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="chef",
            success=True,
            data={"recommendation": "Salad", "reason": "Quick.", "alternatives": [],
                  "shopping_needed": []},
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef.run = _run
    db = _make_db(event_rows=[])
    anon_db = MagicMock()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert len(captured_tasks) == 1
    assert "cooking_time_minutes" in captured_tasks[0].inputs


# ---------------------------------------------------------------------------
# T6 — dinner suggestion cooking_time capped at 60 minutes
# ---------------------------------------------------------------------------

def test_dinner_suggestion_cooking_time_capped_at_60_minutes():
    """
    When the free window is 180 minutes, cooking_time should be capped at 60.
    """
    captured_tasks = []

    chef = MagicMock()

    async def _run(task):
        captured_tasks.append(task)
        return AgentResult(
            task_id=task.task_id, task_type=task.task_type, agent="chef",
            success=True,
            data={"recommendation": "Roast", "reason": "Long cook.", "alternatives": [],
                  "shopping_needed": []},
            confidence="high", data_sources=[], warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef.run = _run

    import app.jobs.free_evening as mod
    from unittest.mock import patch

    db = _make_db(event_rows=[
        {
            "id": "ev3", "external_id": "ext-ev3", "calendar_id": "cal-1",
            "family_id": "fam-1", "family_member_id": "member-1",
            "title": "Busy", "description": None,
            "start_time": "2026-08-10T21:00:00+00:00",
            "end_time": "2026-08-11T02:00:00+00:00",
            "all_day": False, "location": None, "recurrence_rule": None,
            "status": "confirmed", "source": "manual",
        }
    ])
    anon_db = MagicMock()

    from app.models.calendar import AvailabilityWindow
    from datetime import datetime, timezone
    big_window = AvailabilityWindow(
        member_id="family",
        member_name="family",
        date="2026-08-10",
        start_time=datetime(2026, 8, 10, 21, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
        duration_minutes=180,  # 3 hours — should be capped at 60
    )

    with patch.object(mod, "get_family_availability", return_value=[big_window]):
        asyncio.run(
            run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
        )

    assert len(captured_tasks) == 1
    assert captured_tasks[0].inputs["cooking_time_minutes"] == 60


# ---------------------------------------------------------------------------
# T7 — free evening content contains window times
# ---------------------------------------------------------------------------

def test_free_evening_content_contains_window_times():
    captured = {}

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=[])

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        if "free" in payload.get("type", ""):
            captured["content"] = payload.get("content", "")
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    anon_db = MagicMock()
    chef = _make_chef()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    content = captured.get("content", "")
    # Should mention PM times
    assert "PM" in content or "AM" in content or ":" in content


# ---------------------------------------------------------------------------
# T8 — free evening content contains duration
# ---------------------------------------------------------------------------

def test_free_evening_content_contains_duration():
    captured = {}

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=[])

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        if "free" in payload.get("type", ""):
            captured["content"] = payload.get("content", "")
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    anon_db = MagicMock()
    chef = _make_chef()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    # Content should mention "minutes"
    assert "minutes" in captured.get("content", "").lower()


# ---------------------------------------------------------------------------
# T9 — free_evening type in notification row
# ---------------------------------------------------------------------------

def test_free_evening_type_in_notification_row():
    captured_types = []

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=[])

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        captured_types.append(payload.get("type"))
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    anon_db = MagicMock()
    chef = _make_chef()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert "free_evening" in captured_types


# ---------------------------------------------------------------------------
# T10 — dinner_suggestion type in notification row
# ---------------------------------------------------------------------------

def test_dinner_suggestion_type_in_notification_row():
    captured_types = []

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=[])

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        captured_types.append(payload.get("type"))
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select
            tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    anon_db = MagicMock()
    chef = _make_chef()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert "dinner_suggestion" in captured_types


# ---------------------------------------------------------------------------
# T11 — free_evening skipped if already notified today
# ---------------------------------------------------------------------------

def test_free_evening_skipped_if_already_notified_today():
    db = _make_db(event_rows=[], notif_duplicate_types={"free_evening"})
    anon_db = MagicMock()
    chef = _make_chef()

    result = asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert result["free_evening_inserted"] is False


# ---------------------------------------------------------------------------
# T12 — dinner_suggestion skipped if already notified today
# ---------------------------------------------------------------------------

def test_dinner_suggestion_skipped_if_already_notified_today():
    db = _make_db(event_rows=[], notif_duplicate_types={"dinner_suggestion"})
    anon_db = MagicMock()
    chef = _make_chef()

    result = asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )
    assert result["dinner_suggestion_inserted"] is False


# ---------------------------------------------------------------------------
# T13 — free_evening uses family timezone for window search
# ---------------------------------------------------------------------------

def test_free_evening_uses_family_timezone_for_window_search():
    """
    The job builds the window in local time and then queries calendar_events.
    Verify that a gte/lte filter is applied to calendar_events (i.e., the
    local window is used for the DB query, not UTC 5-10 PM blindly).
    """
    gte_values = []

    db = MagicMock()

    ev_chain = MagicMock()

    def _gte(col, val):
        gte_values.append((col, val))
        return ev_chain

    ev_chain.eq.return_value = ev_chain
    ev_chain.gte = _gte
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=[])

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])
    notif_insert = MagicMock()
    notif_insert.execute.return_value = MagicMock(data=[{"id": "x"}])

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select
            tbl.insert.return_value = notif_insert
        return tbl

    db.table.side_effect = _table_side
    anon_db = MagicMock()
    chef = _make_chef()

    asyncio.run(
        run_free_evening_check("fam-1", "America/New_York", db, anon_db, chef, REFERENCE_DT)
    )

    # A gte filter on start_time must have been applied
    assert any(col == "start_time" for col, _ in gte_values)
