"""
Calendar database queries for Family JARVIS.

All application code and agents call these functions — they never write SQL
directly. This is the single source of truth for how calendar data is read
from and written to Supabase.

Security rules enforced here:
- Token columns (access_token_enc, refresh_token_enc) are NEVER returned in
  user-facing queries — they are only read via the admin client in
  get_decrypted_tokens, used exclusively by backend sync logic
- Admin client is used for all writes (RLS blocks user-anon writes)
- User-facing reads always filter by family_id (enforced by RLS at DB level,
  double-enforced here in application code)
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from supabase import Client

from app.providers.calendar.base import CalendarEvent

UTC = ZoneInfo("UTC")


async def get_calendars_for_family(
    family_id: str,
    db: Client,
) -> list[dict]:
    """
    Return calendar rows for the family.

    Token columns are explicitly excluded from the SELECT — they are never
    returned to user-facing code.
    """
    result = (
        db.table("calendars")
        .select(
            "id, family_id, family_member_id, provider, external_id, "
            "name, token_expiry, last_synced_at, active, created_at"
        )
        .eq("family_id", family_id)
        .eq("active", True)
        .execute()
    )
    return result.data or []


async def get_decrypted_tokens(
    calendar_id: str,
    db_admin: Client,
) -> tuple[str, str, datetime]:
    """
    Return (access_token_plain, refresh_token_plain, token_expiry) for a calendar.

    Uses admin client ONLY — tokens are not visible through RLS.
    Called exclusively by backend sync logic, never by user-facing routes.
    """
    result = (
        db_admin.table("calendars")
        .select("access_token_enc, refresh_token_enc, token_expiry")
        .eq("id", calendar_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Calendar {calendar_id} not found")
    row = result.data[0]
    # Tokens are returned encrypted — caller decrypts using encryption.py
    return (
        row["access_token_enc"],
        row["refresh_token_enc"],
        row["token_expiry"],
    )


async def upsert_calendar_events(
    events: list[CalendarEvent],
    db_admin: Client,
) -> int:
    """
    Upsert CalendarEvent objects into the calendar_events table.

    Conflict key: (calendar_id, external_id).
    Uses admin client because user anon client cannot write.

    Returns the number of rows upserted.
    """
    if not events:
        return 0

    rows = [
        {
            "calendar_id": e.calendar_id,
            "family_id": e.family_id,
            "family_member_id": e.family_member_id,
            "external_id": e.external_id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "all_day": e.all_day,
            "location": e.location,
            "recurrence_rule": e.recurrence_rule,
            "status": e.status,
            "source": e.source,
            # raw_data intentionally excluded from storage (verbatim provider JSON
            # would consume significant storage and isn't needed post-normalization)
        }
        for e in events
    ]

    result = (
        db_admin.table("calendar_events")
        .upsert(rows, on_conflict="calendar_id,external_id")
        .execute()
    )
    return len(result.data) if result.data else 0


async def get_events_in_range(
    family_id: str,
    start: datetime,
    end: datetime,
    db: Client,
) -> list[dict]:
    """
    Query calendar_events within a time window for the family.

    Returns raw dicts — caller converts to CalendarEvent as needed.
    RLS enforces family_id at the DB layer; application code also filters
    explicitly as defense-in-depth.
    """
    result = (
        db.table("calendar_events")
        .select("*")
        .eq("family_id", family_id)
        .gte("start_time", start.isoformat())
        .lte("end_time", end.isoformat())
        .order("start_time", desc=False)
        .execute()
    )
    return result.data or []


async def store_calendar_connection(
    family_id: str,
    family_member_id: str,
    provider: str,
    external_id: str,
    name: str,
    access_token_enc: str,
    refresh_token_enc: str,
    token_expiry: datetime,
    db_admin: Client,
) -> str:
    """
    Create or update a calendar row.

    Tokens must already be encrypted — plaintext is never written to the DB.
    Returns the calendar's UUID.
    """
    row = {
        "family_id": family_id,
        "family_member_id": family_member_id,
        "provider": provider,
        "external_id": external_id,
        "name": name,
        "access_token_enc": access_token_enc,
        "refresh_token_enc": refresh_token_enc,
        "token_expiry": token_expiry.isoformat(),
        "active": True,
    }
    result = (
        db_admin.table("calendars")
        .upsert(row, on_conflict="family_member_id,external_id")
        .execute()
    )
    if result.data:
        return result.data[0]["id"]
    raise ValueError("Failed to store calendar connection")


async def update_token(
    calendar_id: str,
    access_token_enc: str,
    token_expiry: datetime,
    db_admin: Client,
) -> None:
    """
    Update the access token after a refresh. Refresh token is NOT touched.

    Only access_token_enc and token_expiry are updated — the refresh token
    remains unchanged (Google only returns a new refresh token on initial auth).
    """
    db_admin.table("calendars").update(
        {
            "access_token_enc": access_token_enc,
            "token_expiry": token_expiry.isoformat(),
        }
    ).eq("id", calendar_id).execute()


async def mark_calendar_synced(
    calendar_id: str,
    db_admin: Client,
) -> None:
    """Update last_synced_at to now() for the given calendar."""
    db_admin.table("calendars").update(
        {"last_synced_at": datetime.now(UTC).isoformat()}
    ).eq("id", calendar_id).execute()
