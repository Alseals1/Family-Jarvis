"""
Evening Briefing Job — Phase 6 background job.

Generates an evening briefing covering tonight and tomorrow for a family,
using OrganizerAgent. If a free window ≥ 60 minutes exists tonight, also
invokes ChefAgent for a dinner suggestion. Scheduled at 22:00 UTC (18:00 US Eastern).

Rules:
- Uses OrganizerAgent with include_summary=True and include_availability=True.
- ChefAgent invoked only when a free window ≥ 60 minutes is found tonight.
- Availability check is pure Python (via organizer result data).
- LLM used only for briefing summary (Organizer) and dinner suggestion (Chef).
- Idempotent: skips if evening_briefing notification already exists for today.
- Never raises — logs errors and returns None on failure.

Notification types:
    NotificationType.evening_briefing  (DB value: 'briefing')
    NotificationType.dinner_suggestion

See plan: plans/phase-6-proactive-intelligence.md § Task 4
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.agents.contracts import AgentTask
from app.agents.organizer import OrganizerAgent
from app.agents.chef import ChefAgent
from app.jobs.notifications import NotificationType, insert_notification

log = logging.getLogger(__name__)
UTC = timezone.utc

# Minimum free window size to trigger a dinner suggestion (minutes)
MIN_WINDOW_FOR_DINNER = 60


def _find_tonight_window(
    availability: list[dict],
    local_date_str: str,
    min_minutes: int = MIN_WINDOW_FOR_DINNER,
) -> dict | None:
    """
    Find the largest free window on local_date_str that is ≥ min_minutes long.

    availability is a list of AvailabilityWindow dicts (serialized by organizer).
    Returns the window dict or None if not found.
    """
    tonight_windows = [
        w for w in availability
        if w.get("date") == local_date_str
        and w.get("duration_minutes", 0) >= min_minutes
    ]
    if not tonight_windows:
        return None
    return max(tonight_windows, key=lambda w: w.get("duration_minutes", 0))


async def run_evening_briefing(
    family_id: str,
    timezone_str: str,
    db_admin,
    organizer: OrganizerAgent,
    chef: ChefAgent,
    reference_dt: datetime | None = None,
) -> str | None:
    """
    Generate an evening briefing covering tonight and tomorrow.

    Args:
        family_id:    UUID of the target family.
        timezone_str: Family timezone string.
        db_admin:     Service-role Supabase client.
        organizer:    OrganizerAgent instance.
        chef:         ChefAgent instance (used if free window found tonight).
        reference_dt: UTC datetime to treat as "now". Defaults to datetime.now(UTC).

    Returns:
        The briefing content string if a new notification was inserted, or None
        if skipped (duplicate) or on error.

    Never raises.
    """
    if reference_dt is None:
        reference_dt = datetime.now(UTC)

    tz = ZoneInfo(timezone_str)
    local_now = reference_dt.astimezone(tz)
    today_local = local_now.date()
    tomorrow_local = today_local + timedelta(days=1)

    start_str = today_local.isoformat()
    end_str = tomorrow_local.isoformat()

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
        context={"job": "evening_briefing", "timezone": timezone_str},
        constraints=[],
        timestamp=reference_dt.isoformat(),
    )

    try:
        result = await organizer.run(task)
    except Exception as exc:
        log.error("evening_briefing_job: organizer failed family=%s err=%s", family_id, exc)
        return None

    summary = (
        result.data.get("briefing_summary")
        or "Good evening. Your schedule overview is ready."
    )

    title = "Good evening — your nightly briefing"
    body = summary

    notif_result = insert_notification(
        db_admin=db_admin,
        family_id=family_id,
        notif_type=NotificationType.evening_briefing,
        title=title,
        body=body,
        trigger_date=today_local,
    )

    if notif_result is None:
        log.info("evening_briefing_job: skipped (already exists) family=%s", family_id)
        return None

    # Check for free window tonight — may trigger a dinner suggestion
    availability = result.data.get("availability", [])
    tonight_window = _find_tonight_window(availability, today_local.isoformat())

    if tonight_window:
        await _maybe_suggest_dinner(
            family_id=family_id,
            db_admin=db_admin,
            chef=chef,
            window=tonight_window,
            today_local=today_local,
        )

    content = f"{title}\n{body}"
    log.info("evening_briefing_job: inserted family=%s id=%s", family_id, notif_result.get("id"))
    return content


async def _maybe_suggest_dinner(
    family_id: str,
    db_admin,
    chef: ChefAgent,
    window: dict,
    today_local,
) -> None:
    """Invoke ChefAgent and store a dinner_suggestion notification if possible."""
    duration = window.get("duration_minutes", 60)
    cooking_time = min(duration, 60)

    task = AgentTask(
        task_id=str(uuid.uuid4()),
        task_type="dinner_suggestion",
        family_id=family_id,
        requested_by="scheduler",
        inputs={
            "cooking_time_minutes": cooking_time,
            "people_eating": 2,
            "budget": "medium",
        },
        context={"job": "evening_briefing", "source": "free_window"},
        constraints=[],
        timestamp=datetime.now(UTC).isoformat(),
    )

    try:
        chef_result = await chef.run(task)
    except Exception as exc:
        log.error("evening_briefing_job: chef failed family=%s err=%s", family_id, exc)
        return

    if not chef_result.success:
        return

    recommendation = chef_result.data.get("recommendation", "")
    reason = chef_result.data.get("reason", "")
    if not recommendation or recommendation == "no_data":
        return

    title = "Dinner idea for tonight"
    body = f"{recommendation}. {reason}"

    insert_notification(
        db_admin=db_admin,
        family_id=family_id,
        notif_type=NotificationType.dinner_suggestion,
        title=title,
        body=body,
        trigger_date=today_local,
    )
