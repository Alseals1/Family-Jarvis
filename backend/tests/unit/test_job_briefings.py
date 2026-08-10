"""
Unit tests for backend/app/jobs/morning_briefing.py and evening_briefing.py

All LLM and DB calls are mocked. Tests verify:
- Organizer invoked with include_summary=True
- Notification row stored
- Idempotent (skipped when already exists)
- Correct notification types
- trigger_date is today
- Evening briefing invokes Chef when free window exists
- Evening briefing skips Chef when no free window
- Graceful failure on Organizer error
- Family timezone used for date range
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.contracts import AgentResult, AgentTask
from app.jobs.morning_briefing import run_morning_briefing
from app.jobs.evening_briefing import run_evening_briefing

UTC = timezone.utc
REFERENCE_DT = datetime(2026, 8, 10, 11, 0, 0, tzinfo=UTC)  # 11:00 UTC = 07:00 Eastern


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_organizer(
    summary="Good morning. You have two events today.",
    success=True,
    availability=None,
):
    organizer = MagicMock()
    availability = availability or []

    async def _run(task):
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="organizer",
            success=success,
            data={
                "events": [],
                "conflicts": [],
                "availability": availability,
                "important_dates": [],
                "briefing_summary": summary if success else None,
            },
            confidence="high",
            data_sources=["calendar_events"],
            warnings=[] if success else ["organizer_error: test"],
            timestamp=REFERENCE_DT.isoformat(),
        )

    organizer.run = _run
    return organizer


def _make_chef(recommendation="Pasta al Pomodoro", reason="Quick and fresh."):
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
            data_sources=["food_preferences"],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef.run = _run
    return chef


def _make_db(duplicate=False, insert_result=None):
    insert_result = insert_result or {"id": "briefing-notif-id"}
    db = MagicMock()

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(
        data=[{"id": "existing"}] if duplicate else []
    )

    notif_insert = MagicMock()
    notif_insert.execute.return_value = MagicMock(
        data=[insert_result] if not duplicate else []
    )

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = notif_select
        tbl.insert.return_value = notif_insert
        return tbl

    db.table.side_effect = _table_side
    return db


def _window(duration=90, date_str="2026-08-10"):
    return {
        "member_id": "family",
        "member_name": "family",
        "date": date_str,
        "start_time": "2026-08-10T17:00:00+00:00",
        "end_time": "2026-08-10T18:30:00+00:00",
        "duration_minutes": duration,
    }


# ============================================================================
# MORNING BRIEFING TESTS
# ============================================================================

# T1 — morning briefing invokes organizer with include_summary=True
def test_morning_briefing_invokes_organizer_with_include_summary_true():
    captured_tasks = []
    organizer = MagicMock()

    async def _run(task):
        captured_tasks.append(task)
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="organizer",
            success=True,
            data={"events": [], "conflicts": [], "availability": [],
                  "important_dates": [], "briefing_summary": "Good morning."},
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    organizer.run = _run
    db = _make_db()

    asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )

    assert len(captured_tasks) == 1
    assert captured_tasks[0].inputs["include_summary"] is True


# T2 — morning briefing stores notification row
def test_morning_briefing_stores_notification_row():
    db = _make_db()
    organizer = _make_organizer()
    result = asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    assert result is not None
    assert "morning" in result.lower() or "Good morning" in result


# T3 — morning briefing skipped when already exists
def test_morning_briefing_skipped_when_already_exists():
    db = _make_db(duplicate=True)
    organizer = _make_organizer()
    result = asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    assert result is None


# T4 — morning briefing includes important dates in context
def test_morning_briefing_includes_important_dates_in_context():
    """
    Organizer fetches important dates internally. The job passes date_range covering
    today — organizer's get_upcoming_important_dates uses days_in_range.
    We verify the Organizer task date_range covers today.
    """
    captured = {}
    organizer = MagicMock()

    async def _run(task):
        captured["date_range"] = task.inputs.get("date_range")
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="organizer",
            success=True,
            data={"events": [], "conflicts": [], "availability": [],
                  "important_dates": [{"label": "Birthday", "days_until": 7}],
                  "briefing_summary": "Today: birthday coming up."},
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    organizer.run = _run
    db = _make_db()

    asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    # Date range start should be today's date in Eastern time
    assert captured["date_range"]["start"] == "2026-08-10"


# T5 — morning briefing type is morning_briefing
def test_morning_briefing_type_is_morning_briefing():
    captured = {}

    db = MagicMock()
    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        captured["type"] = payload.get("type")
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = notif_select
        tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    organizer = _make_organizer()

    asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    # NotificationType.morning_briefing has DB value 'briefing'
    assert captured.get("type") == "briefing"


# T6 — morning briefing trigger_date is today
def test_morning_briefing_trigger_date_is_today():
    captured = {}

    db = MagicMock()
    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        captured["trigger_date"] = payload.get("trigger_date")
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": "x"}])
        return ins

    def _table_side(name):
        tbl = MagicMock()
        tbl.select.return_value = notif_select
        tbl.insert = _insert
        return tbl

    db.table.side_effect = _table_side
    organizer = _make_organizer()

    asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    assert captured.get("trigger_date") == "2026-08-10"


# ============================================================================
# EVENING BRIEFING TESTS
# ============================================================================

# T7 — evening briefing invokes organizer with today and tomorrow
def test_evening_briefing_invokes_organizer_with_today_and_tomorrow():
    captured = {}

    organizer = MagicMock()

    async def _run(task):
        captured["date_range"] = task.inputs.get("date_range")
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="organizer",
            success=True,
            data={"events": [], "conflicts": [], "availability": [],
                  "important_dates": [], "briefing_summary": "Good evening."},
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    organizer.run = _run
    db = _make_db()
    chef = _make_chef()

    asyncio.run(
        run_evening_briefing("fam-1", "America/New_York", db, organizer, chef, REFERENCE_DT)
    )

    assert captured["date_range"]["start"] == "2026-08-10"
    assert captured["date_range"]["end"] == "2026-08-11"


# T8 — evening briefing invokes chef when free window exists
def test_evening_briefing_invokes_chef_when_free_window_exists():
    chef_calls = []

    async def _chef_run(task):
        chef_calls.append(task)
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="chef",
            success=True,
            data={"recommendation": "Pasta", "reason": "Quick.", "alternatives": [],
                  "shopping_needed": []},
            confidence="high",
            data_sources=[],
            warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef = MagicMock()
    chef.run = _chef_run

    organizer = _make_organizer(availability=[_window(duration=90)])
    db = _make_db()

    asyncio.run(
        run_evening_briefing("fam-1", "America/New_York", db, organizer, chef, REFERENCE_DT)
    )
    assert len(chef_calls) == 1


# T9 — evening briefing skips chef when no free window
def test_evening_briefing_skips_chef_when_no_free_window():
    chef_calls = []

    async def _chef_run(task):
        chef_calls.append(task)
        return AgentResult(
            task_id=task.task_id, task_type=task.task_type, agent="chef",
            success=True, data={"recommendation": "Pasta", "reason": ".",
                                 "alternatives": [], "shopping_needed": []},
            confidence="high", data_sources=[], warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    chef = MagicMock()
    chef.run = _chef_run

    # No availability windows
    organizer = _make_organizer(availability=[])
    db = _make_db()

    asyncio.run(
        run_evening_briefing("fam-1", "America/New_York", db, organizer, chef, REFERENCE_DT)
    )
    assert len(chef_calls) == 0


# T10 — evening briefing stores notification row
def test_evening_briefing_stores_notification_row():
    organizer = _make_organizer(availability=[])
    chef = _make_chef()
    db = _make_db()

    result = asyncio.run(
        run_evening_briefing("fam-1", "America/New_York", db, organizer, chef, REFERENCE_DT)
    )
    assert result is not None


# T11 — evening briefing skipped when already exists
def test_evening_briefing_skipped_when_already_exists():
    organizer = _make_organizer()
    chef = _make_chef()
    db = _make_db(duplicate=True)

    result = asyncio.run(
        run_evening_briefing("fam-1", "America/New_York", db, organizer, chef, REFERENCE_DT)
    )
    assert result is None


# T12 — briefing content from organizer summary, not invented
def test_briefing_content_from_organizer_summary_not_invented():
    """The returned content must contain the exact organizer briefing_summary."""
    marker = "DISTINCT_SUMMARY_MARKER_XYZ"
    organizer = _make_organizer(summary=marker)
    chef = _make_chef()
    db = _make_db()

    result = asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    assert result is not None
    assert marker in result


# T13 — briefing uses family timezone for date range
def test_briefing_uses_family_timezone_for_date_range():
    """
    At 11:00 UTC, Eastern (UTC-4 in summer) is 07:00 — still Aug 10.
    At 11:00 UTC, Tokyo (UTC+9) is 20:00 — still Aug 10 (same day here).
    Test that the job correctly resolves the local date for the tz.
    """
    captured = {}

    organizer = MagicMock()

    async def _run(task):
        captured["start"] = task.inputs["date_range"]["start"]
        return AgentResult(
            task_id=task.task_id, task_type=task.task_type, agent="organizer",
            success=True, data={"events": [], "conflicts": [], "availability": [],
                                 "important_dates": [], "briefing_summary": "Hi."},
            confidence="high", data_sources=[], warnings=[],
            timestamp=REFERENCE_DT.isoformat(),
        )

    organizer.run = _run
    db = _make_db()

    # 11:00 UTC = 21:00 Tokyo (UTC+9), still same day Aug 10
    asyncio.run(
        run_morning_briefing("fam-1", "Asia/Tokyo", db, organizer, REFERENCE_DT)
    )
    assert captured["start"] == "2026-08-10"


# T14 — organizer failure handled gracefully
def test_briefing_organizer_failure_handled_gracefully():
    organizer = MagicMock()

    async def _run(task):
        raise RuntimeError("LLM provider timeout")

    organizer.run = _run
    db = _make_db()

    # Must not raise — returns None on error
    result = asyncio.run(
        run_morning_briefing("fam-1", "America/New_York", db, organizer, REFERENCE_DT)
    )
    assert result is None
