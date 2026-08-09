"""
Calendar API routes for Family JARVIS.

Endpoints:
    GET  /api/calendar/status
    GET  /api/calendar/connect/google
    GET  /api/calendar/callback/google?code=&state=
    GET  /api/calendar/events?start=YYYY-MM-DD&end=YYYY-MM-DD
    POST /api/calendar/sync

Security invariants enforced here:
    - All routes require JWT via get_current_user
    - family_id comes from JWT only — never from query params or body
    - OAuth state param is validated server-side (CSRF protection)
    - Token columns never appear in any response
    - POST /sync uses admin client for DB writes; user client for reads
    - Sync is rate-limited to one per family per 5 minutes
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.middleware.auth import get_current_user
from app.config import get_settings
from app.db.queries.calendar import (
    get_calendars_for_family,
    get_events_in_range,
    mark_calendar_synced,
    store_calendar_connection,
    update_token,
    upsert_calendar_events,
    get_decrypted_tokens,
)
from app.db.supabase import get_supabase, get_supabase_admin
from app.logic.availability import get_availability
from app.logic.conflicts import detect_conflicts
from app.logic.dates import parse_date_range
from app.models.calendar import (
    AvailabilityWindow,
    CalendarConnectResponse,
    CalendarConflict,
    CalendarEventResponse,
    CalendarEventsResponse,
    CalendarStatusResponse,
)
from app.providers.calendar.base import CalendarEvent
from app.providers.calendar.encryption import decrypt_token, encrypt_token
from app.providers.calendar.google import GoogleCalendarProvider, TokenExpiredError

UTC = ZoneInfo("UTC")

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# In-memory state (replaced by Redis in production scaling)
_oauth_states: dict[str, str] = {}     # state_token → family_id
_last_sync: dict[str, datetime] = {}   # family_id → last sync timestamp

SYNC_RATE_LIMIT_SECONDS = 300   # 5 minutes


def _require_family(user: dict) -> str:
    fid = user.get("family_id")
    if not fid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family not set up. Complete onboarding first.",
        )
    return fid


def _get_provider() -> GoogleCalendarProvider:
    s = get_settings()
    return GoogleCalendarProvider(
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        redirect_uri=s.google_redirect_uri,
    )


def _dict_to_calendar_event(row: dict) -> CalendarEvent:
    """Convert a DB row dict to a CalendarEvent dataclass."""
    start = datetime.fromisoformat(row["start_time"])
    end = datetime.fromisoformat(row["end_time"])
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return CalendarEvent(
        external_id=row.get("external_id", ""),
        calendar_id=row.get("calendar_id", ""),
        family_id=row.get("family_id", ""),
        family_member_id=row.get("family_member_id", ""),
        title=row.get("title", "Untitled"),
        description=row.get("description"),
        start_time=start,
        end_time=end,
        all_day=row.get("all_day", False),
        location=row.get("location"),
        recurrence_rule=row.get("recurrence_rule"),
        status=row.get("status", "confirmed"),
        source=row.get("source", "manual"),
        raw_data=None,
    )


# ---------------------------------------------------------------------------
# GET /api/calendar/status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status(user: dict = Depends(get_current_user)):
    """Return which calendars are connected for the family."""
    family_id = _require_family(user)
    db = get_supabase()
    calendars = await get_calendars_for_family(family_id, db)
    connected = [
        {
            "id": c.get("id"),
            "member_id": c.get("family_member_id"),
            "provider": c.get("provider"),
            "external_id": c.get("external_id"),
            "name": c.get("name"),
            "last_synced_at": c.get("last_synced_at"),
        }
        for c in calendars
    ]
    return CalendarStatusResponse(
        family_id=family_id,
        connected_calendars=connected,
    )


# ---------------------------------------------------------------------------
# GET /api/calendar/connect/google
# ---------------------------------------------------------------------------

@router.get("/connect/google", response_model=CalendarConnectResponse)
async def connect_google(user: dict = Depends(get_current_user)):
    """
    Initiate Google OAuth flow.

    Generates a UUID state token, stores it server-side for CSRF validation,
    and returns the Google OAuth redirect URL.
    """
    family_id = _require_family(user)
    state = str(uuid.uuid4())
    _oauth_states[state] = family_id

    provider = _get_provider()
    oauth_url = provider.build_oauth_url(state=state)
    return CalendarConnectResponse(oauth_url=oauth_url)


# ---------------------------------------------------------------------------
# GET /api/calendar/callback/google
# ---------------------------------------------------------------------------

@router.get("/callback/google")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """
    Complete Google OAuth flow.

    Validates state param (CSRF), exchanges code for tokens, encrypts them,
    fetches the user's calendar list, stores each calendar in Supabase.
    Token columns are never returned in the response.
    """
    family_id = _require_family(user)

    # CSRF validation: state must exist and match the family
    stored_family = _oauth_states.pop(state, None)
    if stored_family is None or stored_family != family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter",
        )

    s = get_settings()
    if not s.calendar_encryption_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Calendar encryption not configured",
        )

    provider = _get_provider()

    # Exchange authorization code for tokens
    token_data = await provider.exchange_code_for_tokens(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    token_expiry = datetime.now(UTC) + timedelta(seconds=expires_in)

    # Encrypt tokens before storage
    access_enc = encrypt_token(access_token, s.calendar_encryption_key)
    refresh_enc = encrypt_token(refresh_token, s.calendar_encryption_key)

    # Fetch the user's calendars to store connections
    calendars = await provider.get_calendars(access_token)
    db_admin = get_supabase_admin()

    stored_calendars = []
    for cal in calendars:
        cal_id = await store_calendar_connection(
            family_id=family_id,
            family_member_id=user["user_id"],
            provider="google",
            external_id=cal["id"],
            name=cal.get("summary", cal["id"]),
            access_token_enc=access_enc,
            refresh_token_enc=refresh_enc,
            token_expiry=token_expiry,
            db_admin=db_admin,
        )
        stored_calendars.append({"id": cal_id, "name": cal.get("summary")})

    return {
        "connected": True,
        "calendars": stored_calendars,
    }


# ---------------------------------------------------------------------------
# GET /api/calendar/events
# ---------------------------------------------------------------------------

@router.get("/events", response_model=CalendarEventsResponse)
async def get_events(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    user: dict = Depends(get_current_user),
):
    """
    Return events in a date range plus conflict and availability analysis.

    family_id comes from JWT only — query params cannot override it.
    If no calendar is connected, returns empty response with a message.
    """
    family_id = _require_family(user)

    try:
        start_dt, end_dt = parse_date_range(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    db = get_supabase()

    # Check if any calendars connected
    calendars = await get_calendars_for_family(family_id, db)
    if not calendars:
        return CalendarEventsResponse(
            events=[],
            conflicts=[],
            availability=[],
            message="No calendar connected. Visit /api/calendar/connect/google to connect.",
        )

    # Fetch events from DB cache
    raw_events = await get_events_in_range(family_id, start_dt, end_dt, db)
    calendar_events: list[CalendarEvent] = [_dict_to_calendar_event(r) for r in raw_events]

    # Run deterministic logic — no LLM
    conflicts: list[CalendarConflict] = detect_conflicts(calendar_events)

    # Get per-member availability
    member_ids = list({e.family_member_id for e in calendar_events})
    availability: list[AvailabilityWindow] = []
    for member_id in member_ids:
        member_windows = get_availability(
            calendar_events, member_id, start_dt, end_dt
        )
        availability.extend(member_windows)

    # Convert CalendarEvent → CalendarEventResponse (excludes raw_data)
    event_responses = [
        CalendarEventResponse(
            external_id=e.external_id,
            calendar_id=e.calendar_id,
            family_id=e.family_id,
            family_member_id=e.family_member_id,
            title=e.title,
            description=e.description,
            start_time=e.start_time,
            end_time=e.end_time,
            all_day=e.all_day,
            location=e.location,
            recurrence_rule=e.recurrence_rule,
            status=e.status,
            source=e.source,
        )
        for e in calendar_events
    ]

    return CalendarEventsResponse(
        events=event_responses,
        conflicts=conflicts,
        availability=availability,
    )


# ---------------------------------------------------------------------------
# POST /api/calendar/sync
# ---------------------------------------------------------------------------

@router.post("/sync")
async def sync_calendars(user: dict = Depends(get_current_user)):
    """
    Trigger a fresh pull from Google Calendar for all connected calendars.

    Rate-limited: one sync per family per 5 minutes (returns 429 if too soon).
    Uses admin client for DB writes.
    """
    family_id = _require_family(user)

    # Rate limiting
    last = _last_sync.get(family_id)
    if last is not None:
        elapsed = (datetime.now(UTC) - last).total_seconds()
        if elapsed < SYNC_RATE_LIMIT_SECONDS:
            remaining = int(SYNC_RATE_LIMIT_SECONDS - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Sync rate limit reached. Try again in {remaining} seconds.",
            )

    _last_sync[family_id] = datetime.now(UTC)

    s = get_settings()
    db = get_supabase()
    db_admin = get_supabase_admin()

    calendars = await get_calendars_for_family(family_id, db)
    if not calendars:
        return {"synced": 0, "message": "No calendars connected"}

    provider = _get_provider()
    total_synced = 0

    # Fetch last 30 days + next 90 days
    now = datetime.now(UTC)
    sync_start = now - timedelta(days=30)
    sync_end = now + timedelta(days=90)

    for cal in calendars:
        cal_id = cal["id"]
        member_id = cal.get("family_member_id", "")
        external_cal_id = cal.get("external_id", "primary")

        try:
            access_enc, _refresh_enc, _expiry = await get_decrypted_tokens(
                cal_id, db_admin
            )
            if not s.calendar_encryption_key:
                continue
            access_token = decrypt_token(access_enc, s.calendar_encryption_key)
        except (ValueError, Exception):
            continue

        try:
            events = await provider.get_events(
                calendar_id=external_cal_id,
                family_member_id=member_id,
                start=sync_start,
                end=sync_end,
                access_token=access_token,
            )
            # Stamp family_id (provider layer doesn't have it)
            stamped = []
            for e in events:
                stamped.append(CalendarEvent(
                    external_id=e.external_id,
                    calendar_id=cal_id,
                    family_id=family_id,
                    family_member_id=e.family_member_id,
                    title=e.title,
                    description=e.description,
                    start_time=e.start_time,
                    end_time=e.end_time,
                    all_day=e.all_day,
                    location=e.location,
                    recurrence_rule=e.recurrence_rule,
                    status=e.status,
                    source=e.source,
                    raw_data=None,
                ))

            count = await upsert_calendar_events(stamped, db_admin)
            total_synced += count
            await mark_calendar_synced(cal_id, db_admin)

        except TokenExpiredError:
            # Token refresh is handled on next request — skip this calendar
            continue
        except Exception:
            continue

    return {"synced": total_synced}
