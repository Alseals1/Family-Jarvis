"""
Important Dates Alert Job — Phase 6 background job.

Scans all important_dates rows for a family and emits notification rows
when a date is within its lead_days window.

Rules:
- Content is deterministic string formatting — NO LLM.
- Idempotent: dedup check via insert_notification before every insert.
- Yearly-recurring dates use next_occurrence() — pure Python.
- Non-recurring dates are not re-alerted.
- Never raises — logs errors and returns empty list on failure.

Notification types emitted:
    NotificationType.birthday    — for date_type='birthday'
    NotificationType.anniversary — for date_type='anniversary'
    NotificationType.trip_alert  — for date_type='trip'
    NotificationType.birthday    — fallback for all other types (uses 'birthday' DB value)

See plan: plans/phase-6-proactive-intelligence.md § Task 2
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from app.jobs.notifications import NotificationType, insert_notification

log = logging.getLogger(__name__)
UTC = timezone.utc

# Default lead window: alert if event is within this many days
DEFAULT_LEAD_DAYS = 14


def _next_occurrence_of(month: int, day: int, reference: date) -> date:
    """
    Return the next calendar occurrence of (month, day) on or after reference.

    Handles Feb-29 edge case by falling back to Mar-1 in non-leap years.
    """
    try:
        candidate = date(reference.year, month, day)
    except ValueError:
        # Feb 29 in a non-leap year → use Mar 1
        candidate = date(reference.year, 3, 1)

    if candidate >= reference:
        return candidate

    # Try next year
    try:
        return date(reference.year + 1, month, day)
    except ValueError:
        return date(reference.year + 1, 3, 1)


def _format_content(
    date_type: str,
    label: str,
    days: int,
    occurrence: date,
    destination: str | None = None,
) -> tuple[str, str]:
    """
    Build (title, body) strings deterministically — no LLM.

    Returns:
        (title, body) strings ready for insert_notification.
    """
    date_str = occurrence.strftime("%B %-d")  # e.g. "August 17"

    if date_type == "birthday":
        title = f"Birthday: {label}"
        body = f"{label}'s birthday is in {days} days — {date_str}."
    elif date_type == "anniversary":
        title = f"Anniversary: {label}"
        body = f"Your anniversary is in {days} days — {date_str}."
    elif date_type == "trip":
        dest = destination or label
        title = f"Trip: {dest}"
        body = f"Your trip to {dest} departs in {days} days."
    else:
        title = f"Upcoming: {label}"
        body = f"{label} is in {days} days — {date_str}."

    return title, body


async def run_important_date_alerts(
    family_id: str,
    db_admin,
    reference_date: date | None = None,
    lead_days: int = DEFAULT_LEAD_DAYS,
) -> list[str]:
    """
    Scan important_dates for this family and insert alert notifications.

    Args:
        family_id:      UUID string of the family to scan.
        db_admin:       Service-role Supabase client (bypasses RLS).
        reference_date: Date to compute days_until from. Defaults to today UTC.
        lead_days:      Alert window in days. Defaults to 14.

    Returns:
        List of inserted notification IDs (empty if none inserted or error).

    Never raises — logs errors and returns [] on failure.
    """
    if reference_date is None:
        reference_date = datetime.now(UTC).date()

    inserted_ids: list[str] = []

    try:
        result = (
            db_admin.table("important_dates")
            .select("*")
            .eq("family_id", family_id)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.error("important_dates_job: fetch failed family=%s err=%s", family_id, exc)
        return []

    for row in rows:
        try:
            _process_row(
                row=row,
                family_id=family_id,
                db_admin=db_admin,
                reference_date=reference_date,
                lead_days=lead_days,
                inserted_ids=inserted_ids,
            )
        except Exception as exc:
            log.error(
                "important_dates_job: row processing failed family=%s row=%s err=%s",
                family_id,
                row.get("id"),
                exc,
            )

    return inserted_ids


def _process_row(
    row: dict,
    family_id: str,
    db_admin,
    reference_date: date,
    lead_days: int,
    inserted_ids: list[str],
) -> None:
    """Process a single important_date row. Called by run_important_date_alerts."""
    date_type = (row.get("date_type") or row.get("type") or "other").lower()
    label = row.get("label") or row.get("name") or "Event"
    recurring = row.get("recurring", True)
    row_lead = row.get("lead_days", lead_days)
    destination = row.get("destination") or row.get("notes")

    # Parse the stored date — expect YYYY-MM-DD
    raw_date = row.get("date") or row.get("event_date") or row.get("date_value")
    if not raw_date:
        return

    try:
        stored_date = date.fromisoformat(str(raw_date)[:10])
    except (ValueError, TypeError):
        return

    # Compute the next occurrence
    if recurring:
        occurrence = _next_occurrence_of(stored_date.month, stored_date.day, reference_date)
    else:
        occurrence = stored_date
        if occurrence < reference_date:
            # Non-recurring date already passed
            return

    days = (occurrence - reference_date).days

    if days < 0 or days > row_lead:
        # Outside alert window
        return

    # Map date_type → NotificationType
    if date_type == "birthday":
        notif_type = NotificationType.birthday
    elif date_type == "anniversary":
        notif_type = NotificationType.anniversary
    elif date_type == "trip":
        notif_type = NotificationType.trip_alert
    else:
        notif_type = NotificationType.birthday  # fallback uses 'birthday' DB value

    title, body = _format_content(date_type, label, days, occurrence, destination)

    row_result = insert_notification(
        db_admin=db_admin,
        family_id=family_id,
        notif_type=notif_type,
        title=title,
        body=body,
        trigger_date=occurrence,
    )

    if row_result and row_result.get("id"):
        inserted_ids.append(row_result["id"])
