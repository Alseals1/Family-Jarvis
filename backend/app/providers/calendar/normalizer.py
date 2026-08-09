"""
Event normalizer for the Google Calendar API.

This is the boundary layer between Google's wire format and the shared
CalendarEvent dataclass. All Google-specific field names are contained here.
Application code and agents never import or reference Google fields directly.

Security: description and other text fields are stored verbatim.
Prompt injection defense is applied at the agent layer — not here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.providers.calendar.base import CalendarEvent

UTC = ZoneInfo("UTC")

_STATUS_MAP: dict[str, str] = {
    "confirmed": "confirmed",
    "tentative": "tentative",
    "cancelled": "cancelled",
}


def normalize_google_event(
    raw_event: dict,
    calendar_id: str,
    family_id: str,
    family_member_id: str,
) -> CalendarEvent | None:
    """
    Convert a Google Calendar API event dict to a CalendarEvent.

    Returns None if the event should be skipped (e.g., declined invites).

    Raises ValueError if the event is structurally malformed (no 'end' key).
    """
    # Guard: end is required
    if "end" not in raw_event:
        raise ValueError(
            f"Google event {raw_event.get('id', '?')} is missing required 'end' field"
        )

    # Declined invite: skip this event
    for attendee in raw_event.get("attendees", []):
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return None

    # Determine if all-day (Google uses 'date' key for all-day, 'dateTime' for timed)
    start_block = raw_event.get("start", {})
    end_block = raw_event["end"]

    if "date" in start_block:
        # All-day event
        all_day = True
        start_date_str: str = start_block["date"]
        end_date_str: str = end_block.get("date", start_date_str)

        # Parse as midnight UTC on the given date
        start_d = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
            tzinfo=UTC
        )
        end_d = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
            tzinfo=UTC
        )
        # Google all-day end is exclusive (next day) — keep as-is for midnight representation
        start_time = start_d
        end_time = end_d
    else:
        # Timed event
        all_day = False
        start_str: str = start_block.get("dateTime", "")
        end_str: str = end_block.get("dateTime", "")

        start_time = _parse_datetime(start_str)
        end_time = _parse_datetime(end_str)

    # Title
    title: str = raw_event.get("summary", "").strip() or "Untitled Event"

    # Status mapping — unknown statuses default to 'confirmed'
    google_status: str = raw_event.get("status", "confirmed")
    status = _STATUS_MAP.get(google_status, "confirmed")

    return CalendarEvent(
        external_id=raw_event["id"],
        calendar_id=calendar_id,
        family_id=family_id,
        family_member_id=family_member_id,
        title=title,
        description=raw_event.get("description"),  # Stored verbatim — never executed
        start_time=start_time,
        end_time=end_time,
        all_day=all_day,
        location=raw_event.get("location"),
        recurrence_rule=_extract_recurrence(raw_event),
        status=status,
        source="google",
        raw_data=raw_event,  # Full provider payload stored but never trusted
    )


def _parse_datetime(dt_str: str) -> datetime:
    """
    Parse a Google Calendar dateTime string to a UTC-aware datetime.

    Google sends ISO 8601 strings which Python's fromisoformat handles
    correctly in 3.11+. For 3.10 compatibility we handle the 'Z' suffix.
    """
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def _extract_recurrence(raw_event: dict) -> str | None:
    """Extract recurrence rule string from a Google event, or None."""
    recurrence = raw_event.get("recurrence", [])
    for rule in recurrence:
        if rule.startswith("RRULE:"):
            return rule
    return None
