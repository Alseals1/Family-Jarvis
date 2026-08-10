"""
Conflict Alerts Job — Phase 6 background job.

Scans the next N days of calendar events for a family and emits a notification
for each unresolved scheduling conflict.

Rules:
- Reuses detect_conflicts() from logic/conflicts.py — pure Python, no LLM.
- Content strings are deterministic — no LLM.
- Idempotent: dedup on (family_id, 'conflict', trigger_date).
- trigger_date = the date of the conflict (not today).
- Never raises — logs errors and returns [] on failure.

Notification type emitted: NotificationType.conflict_alert

See plan: plans/phase-6-proactive-intelligence.md § Task 3
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.jobs.notifications import NotificationType, insert_notification
from app.logic.conflicts import detect_conflicts
from app.providers.calendar.base import CalendarEvent

log = logging.getLogger(__name__)
UTC = timezone.utc


def _parse_dt(val) -> datetime:
    """Parse an ISO datetime string or passthrough a datetime, ensuring UTC."""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    dt = datetime.fromisoformat(str(val))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _row_to_event(row: dict) -> CalendarEvent:
    """Convert a calendar_events DB row to a CalendarEvent for detect_conflicts()."""
    return CalendarEvent(
        external_id=row.get("external_id", str(row.get("id", ""))),
        calendar_id=row.get("calendar_id", ""),
        family_id=row.get("family_id", ""),
        family_member_id=row.get("family_member_id", ""),
        title=row.get("title", "Untitled"),
        description=row.get("description"),
        start_time=_parse_dt(row["start_time"]),
        end_time=_parse_dt(row["end_time"]),
        all_day=row.get("all_day", False),
        location=row.get("location"),
        recurrence_rule=row.get("recurrence_rule"),
        status=row.get("status", "confirmed"),
        source=row.get("source", "manual"),
        raw_data=None,
    )


def _format_conflict_content(conflict) -> tuple[str, str]:
    """
    Build deterministic (title, body) for a conflict notification.

    Uses conflict.conflict_time.date() as the human-readable day.
    Content format: "Conflict {day}: {member} has {event_a} overlapping {event_b}."
    """
    conflict_day = conflict.conflict_time.strftime("%A, %B %-d")
    title = f"Scheduling conflict: {conflict_day}"
    body = (
        f"Conflict on {conflict_day}: "
        f"{conflict.member_name} has '{conflict.event_a_title}' "
        f"overlapping '{conflict.event_b_title}'."
    )
    return title, body


async def run_conflict_alerts(
    family_id: str,
    db_admin,
    days_ahead: int = 7,
    reference_date: date | None = None,
) -> list[str]:
    """
    Scan the next days_ahead calendar days for conflicts and insert alerts.

    Args:
        family_id:      UUID string of the family to scan.
        db_admin:       Service-role Supabase client (bypasses RLS).
        days_ahead:     How many days forward to scan. Defaults to 7.
        reference_date: Start date. Defaults to today UTC.

    Returns:
        List of inserted notification IDs (empty if none or error).

    Never raises — logs errors and returns [] on failure.
    """
    if reference_date is None:
        reference_date = datetime.now(UTC).date()

    start_dt = datetime(
        reference_date.year, reference_date.month, reference_date.day,
        0, 0, 0, tzinfo=UTC
    )
    end_dt = start_dt + timedelta(days=days_ahead)

    inserted_ids: list[str] = []

    # Fetch calendar events for the window
    try:
        result = (
            db_admin.table("calendar_events")
            .select("*")
            .eq("family_id", family_id)
            .gte("start_time", start_dt.isoformat())
            .lte("start_time", end_dt.isoformat())
            .neq("status", "cancelled")
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.error("conflict_alerts_job: fetch failed family=%s err=%s", family_id, exc)
        return []

    if not rows:
        return []

    # Convert rows to CalendarEvent objects — skip malformed rows
    events: list[CalendarEvent] = []
    for row in rows:
        try:
            events.append(_row_to_event(row))
        except Exception as exc:
            log.warning("conflict_alerts_job: skipping malformed row id=%s err=%s",
                        row.get("id"), exc)

    # detect_conflicts is pure Python — no LLM
    conflicts = detect_conflicts(events)

    for conflict in conflicts:
        try:
            conflict_date = conflict.conflict_time.date()
            title, body = _format_conflict_content(conflict)

            row_result = insert_notification(
                db_admin=db_admin,
                family_id=family_id,
                notif_type=NotificationType.conflict_alert,
                title=title,
                body=body,
                trigger_date=conflict_date,
            )

            if row_result and row_result.get("id"):
                inserted_ids.append(row_result["id"])
        except Exception as exc:
            log.error(
                "conflict_alerts_job: notification insert failed family=%s err=%s",
                family_id, exc
            )

    return inserted_ids
