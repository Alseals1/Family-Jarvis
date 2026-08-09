from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CalendarEventResponse(BaseModel):
    """
    API response shape for a single calendar event.
    Excludes raw_data — provider payloads are never returned to clients.
    """

    external_id: str
    calendar_id: str
    family_id: str
    family_member_id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool
    location: Optional[str] = None
    recurrence_rule: Optional[str] = None
    status: str   # 'confirmed' | 'tentative' | 'cancelled'
    source: str   # 'google' | 'apple' | 'outlook' | 'manual'


class CalendarConflict(BaseModel):
    """A same-member scheduling overlap."""

    conflict_time: datetime          # Start of the overlapping window
    member_id: str
    member_name: str
    event_a_title: str
    event_b_title: str
    overlap_minutes: int


class AvailabilityWindow(BaseModel):
    """A contiguous free window for one family member."""

    member_id: str
    member_name: str
    date: str                        # ISO date string, e.g. '2026-08-14'
    start_time: datetime
    end_time: datetime
    duration_minutes: int


class CalendarEventsResponse(BaseModel):
    """Top-level response for GET /api/calendar/events."""

    events: list[CalendarEventResponse]
    conflicts: list[CalendarConflict]
    availability: list[AvailabilityWindow]
    message: Optional[str] = None    # Set when no calendar is connected


class CalendarStatusResponse(BaseModel):
    """Which calendars are connected for the family."""

    family_id: str
    connected_calendars: list[dict]  # {member_id, member_name, provider, external_id, name}


class CalendarConnectResponse(BaseModel):
    """OAuth initiation response."""

    oauth_url: str
