"""
Family data access layer for the Manager Agent.

Wraps DB queries and Phase 3 calendar/dates logic into a clean interface.
All agents call this — never raw Supabase queries directly from agent code.

Security rules:
- family_id always comes from JWT, never from request body (enforced by callers)
- Token columns are never queried or returned
- Admin client used only where required (memory writes)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from supabase import Client

from app.db.queries.calendar import get_events_in_range
from app.logic.conflicts import detect_conflicts
from app.logic.availability import get_family_availability
from app.logic.dates import days_until, next_occurrence
from app.providers.calendar.base import CalendarEvent
from app.models.calendar import CalendarConflict, AvailabilityWindow

UTC = ZoneInfo("UTC")


def _row_to_calendar_event(row: dict) -> CalendarEvent:
    """Convert a calendar_events DB row to a CalendarEvent dataclass."""
    def _parse_dt(val: str | datetime) -> datetime:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=UTC)
        dt = datetime.fromisoformat(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    return CalendarEvent(
        external_id=row["external_id"],
        calendar_id=row["calendar_id"],
        family_id=row["family_id"],
        family_member_id=row["family_member_id"],
        title=row["title"],
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


class FamilyDataFetcher:
    def __init__(self, db: Client, db_admin: Client) -> None:
        self._db = db
        self._db_admin = db_admin

    async def get_calendar_events_and_analysis(
        self,
        family_id: str,
        start: datetime,
        end: datetime,
    ) -> dict:
        """
        Fetch calendar events for the family in the date range, run conflict
        detection and availability calculation, and return a combined result.

        Returns:
            {
                "events": list[dict],          # serializable event summaries
                "conflicts": list[dict],        # conflict summaries
                "availability": list[dict],     # availability windows
                "member_ids": list[str],        # family member IDs in range
            }
        """
        rows = await get_events_in_range(family_id, start, end, self._db)
        events = [_row_to_calendar_event(r) for r in rows]

        conflicts: list[CalendarConflict] = detect_conflicts(events)

        member_ids = list({e.family_member_id for e in events})
        availability: list[AvailabilityWindow] = get_family_availability(
            events=events,
            member_ids=member_ids,
            date_range_start=start,
            date_range_end=end,
        )

        return {
            "events": [
                {
                    "title": e.title,
                    "member_id": e.family_member_id,
                    "start": e.start_time.isoformat(),
                    "end": e.end_time.isoformat(),
                    "all_day": e.all_day,
                    "status": e.status,
                }
                for e in events
                if e.status != "cancelled"
            ],
            "conflicts": [
                {
                    "member_id": c.member_id,
                    "member_name": c.member_name,
                    "event_a": c.event_a_title,
                    "event_b": c.event_b_title,
                    "conflict_time": c.conflict_time.isoformat(),
                    "overlap_minutes": c.overlap_minutes,
                }
                for c in conflicts
            ],
            "availability": [
                {
                    "member_id": w.member_id,
                    "date": w.date.isoformat() if isinstance(w.date, date) else w.date,
                    "start_minute": w.start_minute,
                    "end_minute": w.end_minute,
                }
                for w in availability
            ],
            "member_ids": member_ids,
        }

    async def get_upcoming_important_dates(
        self,
        family_id: str,
        days_ahead: int = 30,
    ) -> list[dict]:
        """
        Return upcoming important dates sorted by days_until.
        Uses next_occurrence for yearly-recurring dates.
        """
        result = (
            self._db_admin.table("important_dates")
            .select("id, label, date_type, date, family_member_id, recurs_yearly, notes, lead_days")
            .eq("family_id", family_id)
            .execute()
        )
        rows = result.data or []
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        upcoming = []
        for row in rows:
            raw_date = date.fromisoformat(row["date"])
            if row.get("recurs_yearly", True):
                occurrence = next_occurrence(raw_date, today)
            else:
                occurrence = raw_date

            if today <= occurrence <= cutoff:
                upcoming.append(
                    {
                        "label": row["label"],
                        "date_type": row["date_type"],
                        "date": occurrence.isoformat(),
                        "days_until": days_until(occurrence, today),
                        "family_member_id": row.get("family_member_id"),
                        "notes": row.get("notes"),
                    }
                )

        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    async def get_family_members(
        self,
        family_id: str,
    ) -> list[dict]:
        """
        Return family member list (id, name, relationship).
        Used to provide name context to the Manager's system prompt.
        """
        result = (
            self._db.table("family_members")
            .select("id, name, relationship")
            .eq("family_id", family_id)
            .eq("active", True)
            .execute()
        )
        return result.data or []

    async def save_memory(
        self,
        family_id: str,
        content: str,
        category: str,
    ) -> str:
        """
        Insert a memory into the memories table.
        Returns a confirmation string suitable for reading aloud to the user.
        """
        self._db_admin.table("memories").insert(
            {
                "family_id": family_id,
                "content": content,
                "category": category,
                "source": "conversation",
            }
        ).execute()
        return f"Got it — I've saved that to memory: \"{content}\""
