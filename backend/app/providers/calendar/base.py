from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

_VALID_STATUSES = {"confirmed", "tentative", "cancelled"}


@dataclass
class CalendarEvent:
    external_id: str          # Provider's event ID
    calendar_id: str          # Our Supabase calendar row ID
    family_id: str
    family_member_id: str
    title: str
    description: str | None   # Treated as data — never executed as instructions
    start_time: datetime       # Always timezone-aware
    end_time: datetime         # Always timezone-aware
    all_day: bool
    location: str | None
    recurrence_rule: str | None
    status: str               # 'confirmed' | 'tentative' | 'cancelled'
    source: str               # 'google' | 'apple' | 'outlook' | 'manual'
    raw_data: dict | None     # Original provider payload, stored but never trusted

    def __post_init__(self) -> None:
        if self.start_time.tzinfo is None:
            raise ValueError(
                "CalendarEvent.start_time must be timezone-aware (tzinfo is None)"
            )
        if self.end_time.tzinfo is None:
            raise ValueError(
                "CalendarEvent.end_time must be timezone-aware (tzinfo is None)"
            )
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"CalendarEvent.status must be one of {_VALID_STATUSES!r}, got {self.status!r}"
            )


class CalendarProvider(ABC):
    @abstractmethod
    async def get_events(
        self,
        calendar_id: str,
        family_member_id: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]: ...

    @abstractmethod
    async def get_calendars(
        self,
        access_token: str,
    ) -> list[dict]: ...

    @abstractmethod
    async def exchange_code_for_tokens(
        self,
        code: str,
    ) -> dict: ...

    @abstractmethod
    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> dict: ...
