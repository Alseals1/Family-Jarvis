"""
Unit tests for backend/app/jobs/conflict_alerts.py

All DB calls are mocked. Tests verify:
- Conflict alert inserted when conflict exists
- No alert when no conflicts
- Content contains member name and event titles
- Content contains conflict time
- Duplicate skipped
- Correct notification type
- detect_conflicts used (not LLM)
- Multiple conflicts → multiple notifications
- Cancelled events excluded from conflict scan
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.jobs.conflict_alerts import run_conflict_alerts

UTC = timezone.utc
REFERENCE = date(2026, 8, 10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event_row(
    member_id="member-1",
    title="Soccer Practice",
    start_hour=10,
    end_hour=11,
    status="confirmed",
    day_offset=0,
):
    base = datetime(2026, 8, 10 + day_offset, start_hour, 0, tzinfo=UTC)
    end = datetime(2026, 8, 10 + day_offset, end_hour, 0, tzinfo=UTC)
    return {
        "id": f"ev-{member_id}-{title[:4]}-{start_hour}",
        "external_id": f"ext-{member_id}-{title[:4]}-{start_hour}",
        "calendar_id": "cal-1",
        "family_id": "fam-1",
        "family_member_id": member_id,
        "title": title,
        "description": None,
        "start_time": base.isoformat(),
        "end_time": end.isoformat(),
        "all_day": False,
        "location": None,
        "recurrence_rule": None,
        "status": status,
        "source": "manual",
    }


def _make_db(event_rows=None, insert_result=None, duplicate=False):
    event_rows = event_rows or []
    insert_result = insert_result or {"id": "notif-1"}

    db = MagicMock()

    # calendar_events query chain
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=event_rows)

    # notifications dedup chain
    notif_select_chain = MagicMock()
    notif_select_chain.eq.return_value = notif_select_chain
    if duplicate:
        notif_select_chain.execute.return_value = MagicMock(data=[{"id": "existing"}])
    else:
        notif_select_chain.execute.return_value = MagicMock(data=[])

    notif_insert_chain = MagicMock()
    notif_insert_chain.execute.return_value = MagicMock(
        data=[insert_result] if insert_result else []
    )

    def _table_side(name):
        tbl = MagicMock()
        if name == "calendar_events":
            tbl.select.return_value = ev_chain
        else:
            tbl.select.return_value = notif_select_chain
            tbl.insert.return_value = notif_insert_chain
        return tbl

    db.table.side_effect = _table_side
    return db


def _overlapping_events():
    """Two events for same member that overlap — produces 1 conflict."""
    return [
        _make_event_row("member-A", "Soccer Practice", start_hour=10, end_hour=12),
        _make_event_row("member-A", "Piano Lesson",   start_hour=11, end_hour=13),
    ]


# ---------------------------------------------------------------------------
# T1 — conflict alert inserted when conflict found
# ---------------------------------------------------------------------------

def test_conflict_alert_inserted_when_conflict_found():
    db = _make_db(event_rows=_overlapping_events())
    result = asyncio.run(
        run_conflict_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert len(result) == 1
    assert result[0] == "notif-1"


# ---------------------------------------------------------------------------
# T2 — no alert when no conflicts
# ---------------------------------------------------------------------------

def test_no_alert_when_no_conflicts():
    events = [
        _make_event_row("member-A", "Morning Run",    start_hour=7,  end_hour=8),
        _make_event_row("member-B", "Soccer Practice", start_hour=10, end_hour=11),
    ]
    db = _make_db(event_rows=events)
    result = asyncio.run(
        run_conflict_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []


# ---------------------------------------------------------------------------
# T3 — content contains member name
# ---------------------------------------------------------------------------

def test_conflict_alert_content_contains_member_name():
    captured = {}

    db = MagicMock()

    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=_overlapping_events())

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
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

    asyncio.run(run_conflict_alerts("fam-1", db, reference_date=REFERENCE))
    # member_name on CalendarConflict is set from CalendarEvent.family_member_id
    assert "member-A" in captured.get("content", "")


# ---------------------------------------------------------------------------
# T4 — content contains event titles
# ---------------------------------------------------------------------------

def test_conflict_alert_content_contains_event_titles():
    captured = {}

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=_overlapping_events())

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
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

    asyncio.run(run_conflict_alerts("fam-1", db, reference_date=REFERENCE))
    content = captured.get("content", "")
    assert "Soccer Practice" in content
    assert "Piano Lesson" in content


# ---------------------------------------------------------------------------
# T5 — content contains conflict time/date
# ---------------------------------------------------------------------------

def test_conflict_alert_content_contains_conflict_time():
    captured = {}

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=_overlapping_events())

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
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

    asyncio.run(run_conflict_alerts("fam-1", db, reference_date=REFERENCE))
    content = captured.get("content", "")
    # Should contain a day name or date
    assert any(day in content for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "August", "10"])


# ---------------------------------------------------------------------------
# T6 — alert skipped when duplicate exists
# ---------------------------------------------------------------------------

def test_conflict_alert_skipped_when_duplicate_exists():
    db = _make_db(event_rows=_overlapping_events(), duplicate=True)
    result = asyncio.run(
        run_conflict_alerts("fam-1", db, reference_date=REFERENCE)
    )
    assert result == []


# ---------------------------------------------------------------------------
# T7 — conflict type in notification row
# ---------------------------------------------------------------------------

def test_conflict_type_in_notification_row():
    captured = {}

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=_overlapping_events())

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    def _insert(payload):
        captured["type"] = payload.get("type", "")
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

    asyncio.run(run_conflict_alerts("fam-1", db, reference_date=REFERENCE))
    assert captured.get("type") == "conflict"


# ---------------------------------------------------------------------------
# T8 — conflict detection uses logic not LLM
# ---------------------------------------------------------------------------

def test_conflict_detection_uses_logic_not_llm():
    """Verify detect_conflicts is called and no LLM imports exist."""
    import app.jobs.conflict_alerts as mod
    import inspect
    source = inspect.getsource(mod)
    assert "LLMProvider" not in source
    assert "openrouter" not in source
    assert "detect_conflicts" in source


# ---------------------------------------------------------------------------
# T9 — multiple conflicts generate multiple notifications
# ---------------------------------------------------------------------------

def test_multiple_conflicts_generate_multiple_notifications():
    """Three overlapping events for the same member → 3 conflict pairs."""
    events = [
        _make_event_row("member-A", "Event 1", start_hour=10, end_hour=14),
        _make_event_row("member-A", "Event 2", start_hour=11, end_hour=15),
        _make_event_row("member-A", "Event 3", start_hour=12, end_hour=16),
    ]

    ids = []

    db = MagicMock()
    ev_chain = MagicMock()
    ev_chain.eq.return_value = ev_chain
    ev_chain.gte.return_value = ev_chain
    ev_chain.lte.return_value = ev_chain
    ev_chain.neq.return_value = ev_chain
    ev_chain.execute.return_value = MagicMock(data=events)

    notif_select = MagicMock()
    notif_select.eq.return_value = notif_select
    notif_select.execute.return_value = MagicMock(data=[])

    counter = [0]

    def _insert(payload):
        counter[0] += 1
        ins = MagicMock()
        ins.execute.return_value = MagicMock(data=[{"id": f"notif-{counter[0]}"}])
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

    result = asyncio.run(
        run_conflict_alerts("fam-1", db, reference_date=REFERENCE)
    )
    # 3 events for one member → C(3,2) = 3 pairs → 3 conflicts
    assert len(result) == 3


# ---------------------------------------------------------------------------
# T10 — cancelled events excluded from conflict scan
# ---------------------------------------------------------------------------

def test_cancelled_events_excluded_from_conflict_scan():
    """A cancelled event should not participate in conflict detection."""
    events = [
        _make_event_row("member-A", "Soccer Practice", start_hour=10, end_hour=12, status="confirmed"),
        _make_event_row("member-A", "Piano Lesson",    start_hour=11, end_hour=13, status="cancelled"),
    ]
    db = _make_db(event_rows=events)
    result = asyncio.run(
        run_conflict_alerts("fam-1", db, reference_date=REFERENCE)
    )
    # Cancelled event excluded — no conflict
    assert result == []
