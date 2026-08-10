"""
Free Evening and Dinner Suggestion Job — Phase 6 background job.

Checks tonight's family calendar for a shared free window (5 PM → 10 PM).
If a window ≥ 45 minutes is found:
  1. Emits a 'free_evening' notification with window start/end and duration.
  2. Invokes ChefAgent for a dinner suggestion (cooking_time = min(window, 60)).
  3. Emits a 'dinner_suggestion' notification with the recommendation.

Scheduled at 20:00 UTC (16:00 US Eastern).

Rules:
- Availability check is pure Python (get_availability from logic/availability.py).
- Chef is the only LLM call.
- Content strings are deterministic except for Chef recommendation.
- Idempotent: dedup per (family_id, type, trigger_date).
- Never raises — logs errors and returns result dict on partial failure.

See plan: plans/phase-6-proactive-intelligence.md § Task 5
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.agents.contracts import AgentTask
from app.agents.chef import ChefAgent
from app.jobs.notifications import NotificationType, insert_notification
from app.logic.availability import get_family_availability
from app.providers.calendar.base import CalendarEvent

log = logging.getLogger(__name__)
UTC = timezone.utc

# Window: 5 PM → 10 PM local time (tonight)
WINDOW_START_HOUR = 17
WINDOW_END_HOUR = 22

# Minimum free window to trigger notifications
MIN_FREE_MINUTES = 45

# Cap cooking time at 60 minutes
MAX_COOKING_TIME = 60


def _parse_dt(val) -> datetime:
    """Parse ISO string or passthrough datetime, ensuring UTC-aware."""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    dt = datetime.fromisoformat(str(val))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _row_to_event(row: dict) -> CalendarEvent:
    """Convert a calendar_events DB row to CalendarEvent."""
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


def _format_time(dt: datetime, tz: "ZoneInfo") -> str:
    """Format a UTC datetime as local HH:MM (no seconds)."""
    local = dt.astimezone(tz)
    return local.strftime("%-I:%M %p")


async def run_free_evening_check(
    family_id: str,
    timezone_str: str,
    db_admin,
    db,
    chef: ChefAgent,
    reference_dt: datetime | None = None,
    min_free_minutes: int = MIN_FREE_MINUTES,
) -> dict:
    """
    Check tonight for a shared free window and optionally suggest dinner.

    Args:
        family_id:       UUID of the family to check.
        timezone_str:    Family timezone string.
        db_admin:        Service-role Supabase client (bypasses RLS).
        db:              Anon Supabase client (for calendar event queries).
        chef:            ChefAgent instance.
        reference_dt:    UTC datetime to treat as "now". Defaults to datetime.now(UTC).
        min_free_minutes: Minimum window size in minutes. Defaults to 45.

    Returns:
        dict with keys:
            "free_evening_inserted": bool
            "dinner_suggestion_inserted": bool
            "window": dict | None  — the found window or None

    Never raises.
    """
    result = {
        "free_evening_inserted": False,
        "dinner_suggestion_inserted": False,
        "window": None,
    }

    if reference_dt is None:
        reference_dt = datetime.now(UTC)

    tz = ZoneInfo(timezone_str)
    local_now = reference_dt.astimezone(tz)
    today_local = local_now.date()

    # Build tonight's window in UTC
    window_start_local = datetime(
        today_local.year, today_local.month, today_local.day,
        WINDOW_START_HOUR, 0, tzinfo=tz
    )
    window_end_local = datetime(
        today_local.year, today_local.month, today_local.day,
        WINDOW_END_HOUR, 0, tzinfo=tz
    )
    window_start_utc = window_start_local.astimezone(UTC)
    window_end_utc = window_end_local.astimezone(UTC)

    # Fetch events for all family members in tonight's window
    try:
        ev_result = (
            db_admin.table("calendar_events")
            .select("*")
            .eq("family_id", family_id)
            .gte("start_time", window_start_utc.isoformat())
            .lte("start_time", window_end_utc.isoformat())
            .neq("status", "cancelled")
            .execute()
        )
        rows = ev_result.data or []
    except Exception as exc:
        log.error("free_evening_job: event fetch failed family=%s err=%s", family_id, exc)
        return result

    events: list[CalendarEvent] = []
    for row in rows:
        try:
            events.append(_row_to_event(row))
        except Exception as exc:
            log.warning("free_evening_job: skipping malformed row err=%s", exc)

    # Get distinct member IDs from events (or use a small default set)
    member_ids = list({e.family_member_id for e in events})
    if not member_ids:
        # No events tonight → everyone is free
        window_minutes = int((window_end_utc - window_start_utc).total_seconds() / 60)
        free_window = {
            "start": window_start_utc.isoformat(),
            "end": window_end_utc.isoformat(),
            "duration_minutes": window_minutes,
        }
        result["window"] = free_window
    else:
        # Use availability logic — pure Python
        windows = get_family_availability(
            events=events,
            member_ids=member_ids,
            date_range_start=window_start_utc,
            date_range_end=window_end_utc,
            min_window_minutes=min_free_minutes,
        )

        if not windows:
            return result  # No free window tonight

        # Pick the largest window
        best = max(windows, key=lambda w: w.duration_minutes)
        free_window = {
            "start": best.start_time.isoformat(),
            "end": best.end_time.isoformat(),
            "duration_minutes": best.duration_minutes,
        }
        result["window"] = free_window

    if result["window"] is None or result["window"]["duration_minutes"] < min_free_minutes:
        return result

    window = result["window"]
    duration = window["duration_minutes"]
    start_fmt = _format_time(_parse_dt(window["start"]), tz)
    end_fmt = _format_time(_parse_dt(window["end"]), tz)

    # --- Emit free_evening notification ---
    fe_title = "Free evening tonight"
    fe_body = (
        f"Everyone's free tonight from {start_fmt} to {end_fmt}. "
        f"You have about {duration} minutes for dinner."
    )
    fe_result = insert_notification(
        db_admin=db_admin,
        family_id=family_id,
        notif_type=NotificationType.free_evening,
        title=fe_title,
        body=fe_body,
        trigger_date=today_local,
    )
    result["free_evening_inserted"] = fe_result is not None

    # --- Invoke ChefAgent for dinner suggestion ---
    cooking_time = min(duration, MAX_COOKING_TIME)
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
        context={"job": "free_evening", "window_minutes": duration},
        constraints=[],
        timestamp=reference_dt.isoformat(),
    )

    try:
        chef_result = await chef.run(task)
    except Exception as exc:
        log.error("free_evening_job: chef failed family=%s err=%s", family_id, exc)
        return result

    if chef_result.success:
        recommendation = chef_result.data.get("recommendation", "")
        reason = chef_result.data.get("reason", "")
        if recommendation and recommendation != "no_data":
            ds_title = "Dinner idea for tonight"
            ds_body = f"Dinner idea for tonight: {recommendation}. {reason}"
            ds_result = insert_notification(
                db_admin=db_admin,
                family_id=family_id,
                notif_type=NotificationType.dinner_suggestion,
                title=ds_title,
                body=ds_body,
                trigger_date=today_local,
            )
            result["dinner_suggestion_inserted"] = ds_result is not None

    return result
