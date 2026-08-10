"""
Morning Briefing Job — Phase 6 background job.

Generates a morning briefing for a family using OrganizerAgent and stores it
as a notification row. Scheduled at 11:00 UTC (07:00 US Eastern).

Rules:
- Uses OrganizerAgent with include_summary=True — same path as chat route.
- LLM called only for the natural-language briefing summary.
- Date range calculation is pure Python.
- Idempotent: skips if morning_briefing notification already exists for today.
- Never raises — logs errors and returns None on failure.

Notification type: NotificationType.morning_briefing (DB value: 'briefing')

See plan: plans/phase-6-proactive-intelligence.md § Task 4
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.agents.contracts import AgentTask
from app.agents.organizer import OrganizerAgent
from app.jobs.notifications import NotificationType, insert_notification

log = logging.getLogger(__name__)
UTC = timezone.utc


async def run_morning_briefing(
    family_id: str,
    timezone_str: str,
    db_admin,
    organizer: OrganizerAgent,
    reference_dt: datetime | None = None,
) -> str | None:
    """
    Generate a morning briefing for the family and store as a notification.

    Args:
        family_id:    UUID of the target family.
        timezone_str: Family timezone string (e.g. "America/New_York"). Used to
                      compute local "today" for the date range.
        db_admin:     Service-role Supabase client (bypasses RLS).
        organizer:    OrganizerAgent instance (LLM + DB wired in by scheduler).
        reference_dt: UTC datetime to treat as "now". Defaults to datetime.now(UTC).

    Returns:
        The briefing content string if a new notification was inserted, or None
        if skipped (duplicate already exists) or on error.

    Never raises.
    """
    if reference_dt is None:
        reference_dt = datetime.now(UTC)

    # Convert to family local time to determine "today"
    tz = ZoneInfo(timezone_str)
    local_now = reference_dt.astimezone(tz)
    today_local = local_now.date()

    # Date range: today midnight → 11:59 PM in local time
    start_str = today_local.isoformat()
    end_str = today_local.isoformat()

    task = AgentTask(
        task_id=str(uuid.uuid4()),
        task_type="calendar_query",
        family_id=family_id,
        requested_by="scheduler",
        inputs={
            "date_range": {"start": start_str, "end": end_str},
            "members": ["all"],
            "include_summary": True,
            "include_availability": True,
        },
        context={"job": "morning_briefing", "timezone": timezone_str},
        constraints=[],
        timestamp=reference_dt.isoformat(),
    )

    try:
        result = await organizer.run(task)
    except Exception as exc:
        log.error("morning_briefing_job: organizer failed family=%s err=%s", family_id, exc)
        return None

    if not result.success:
        log.warning(
            "morning_briefing_job: organizer returned success=False family=%s warnings=%s",
            family_id, result.warnings
        )
        # Use warnings as fallback content if briefing_summary is absent
        summary = result.data.get("briefing_summary") or "Morning briefing unavailable."
    else:
        summary = result.data.get("briefing_summary") or "Good morning. Your schedule is clear."

    title = "Good morning — your daily briefing"
    body = summary

    row_result = insert_notification(
        db_admin=db_admin,
        family_id=family_id,
        notif_type=NotificationType.morning_briefing,
        title=title,
        body=body,
        trigger_date=today_local,
    )

    if row_result is None:
        log.info("morning_briefing_job: skipped (already exists) family=%s", family_id)
        return None

    content = f"{title}\n{body}"
    log.info("morning_briefing_job: inserted family=%s id=%s", family_id, row_result.get("id"))
    return content
