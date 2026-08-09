"""
Availability calculation for Family JARVIS.

Given a list of CalendarEvent objects, determines free windows within a
requested time range. Used by the Organizer Agent and Date Planner Agent.

This module is pure Python — no LLM, no DB, no HTTP.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.providers.calendar.base import CalendarEvent
from app.models.calendar import AvailabilityWindow

UTC = ZoneInfo("UTC")


def get_availability(
    events: list[CalendarEvent],
    family_member_id: str,
    date_range_start: datetime,
    date_range_end: datetime,
    min_window_minutes: int = 30,
    day_start_hour: int = 8,
    day_end_hour: int = 22,
) -> list[AvailabilityWindow]:
    """
    Given events for any set of members, return free windows for the specified
    member within the date range.

    Rules:
    - Only hours between day_start_hour and day_end_hour are considered
    - Cancelled events are ignored
    - All-day events block the entire day (day_start to day_end)
    - Windows shorter than min_window_minutes are not returned
    """
    # Filter to this member only, excluding cancelled
    member_events = [
        e for e in events
        if e.family_member_id == family_member_id
        and e.status != "cancelled"
    ]

    windows: list[AvailabilityWindow] = []

    # Iterate day by day across the range
    current = date_range_start.date() if hasattr(date_range_start, "date") else date_range_start
    end_date = date_range_end.date() if hasattr(date_range_end, "date") else date_range_end

    # Ensure we iterate over whole days
    if isinstance(date_range_start, datetime):
        current = date_range_start.date()
    if isinstance(date_range_end, datetime):
        end_date = date_range_end.date()

    current_date = current
    end_date_val = end_date

    while current_date < end_date_val:
        day_start = datetime(
            current_date.year, current_date.month, current_date.day,
            day_start_hour, 0, tzinfo=UTC
        )
        day_end = datetime(
            current_date.year, current_date.month, current_date.day,
            day_end_hour, 0, tzinfo=UTC
        )

        # Collect busy intervals for this day
        busy: list[tuple[datetime, datetime]] = []
        all_day_blocked = False

        for event in member_events:
            # Check if event falls on this day
            event_start = event.start_time.astimezone(UTC)
            event_end = event.end_time.astimezone(UTC)

            if event.all_day:
                # All-day event: check if it covers this day
                event_day = event_start.date()
                event_end_day = event_end.date()
                if event_day <= current_date < event_end_day:
                    all_day_blocked = True
                    break
            else:
                # Timed event: check for overlap with this day's window
                if event_end > day_start and event_start < day_end:
                    # Clamp to day boundaries
                    busy_start = max(event_start, day_start)
                    busy_end = min(event_end, day_end)
                    busy.append((busy_start, busy_end))

        if all_day_blocked:
            current_date += timedelta(days=1)
            continue

        # Sort and merge overlapping busy intervals
        busy.sort(key=lambda x: x[0])
        merged: list[tuple[datetime, datetime]] = []
        for start, end in busy:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Find free gaps
        free_start = day_start
        for busy_start, busy_end in merged:
            if busy_start > free_start:
                gap_minutes = int((busy_start - free_start).total_seconds() / 60)
                if gap_minutes >= min_window_minutes:
                    windows.append(_make_window(
                        family_member_id, current_date, free_start, busy_start
                    ))
            free_start = max(free_start, busy_end)

        # Check gap after last busy interval
        if day_end > free_start:
            gap_minutes = int((day_end - free_start).total_seconds() / 60)
            if gap_minutes >= min_window_minutes:
                windows.append(_make_window(
                    family_member_id, current_date, free_start, day_end
                ))

        current_date += timedelta(days=1)

    return windows


def get_family_availability(
    events: list[CalendarEvent],
    member_ids: list[str],
    date_range_start: datetime,
    date_range_end: datetime,
    min_window_minutes: int = 60,
) -> list[AvailabilityWindow]:
    """
    Return windows where ALL listed members are free simultaneously.

    Computes availability per member then intersects across all members.
    """
    if not member_ids:
        return []

    # Get availability for each member (use 1-min minimum to capture all windows)
    per_member: list[list[AvailabilityWindow]] = []
    for member_id in member_ids:
        member_windows = get_availability(
            events,
            member_id,
            date_range_start,
            date_range_end,
            min_window_minutes=1,  # We'll filter after intersection
        )
        per_member.append(member_windows)

    # Use first member's windows as the base
    result: list[AvailabilityWindow] = []
    base_windows = per_member[0]

    for base_window in base_windows:
        # Find intersection with every other member's windows
        current_start = base_window.start_time
        current_end = base_window.end_time

        for other_windows in per_member[1:]:
            # Find if any other_window overlaps with [current_start, current_end]
            new_start = None
            new_end = None
            for other in other_windows:
                overlap_start = max(current_start, other.start_time)
                overlap_end = min(current_end, other.end_time)
                if overlap_start < overlap_end:
                    if new_start is None or overlap_start < new_start:
                        new_start = overlap_start
                    if new_end is None or overlap_end > new_end:
                        new_end = overlap_end

            if new_start is None:
                # No overlap with this member → whole window blocked
                current_start = current_end  # collapse window to zero
                break
            current_start = new_start
            current_end = new_end

        # Check if resulting window is large enough
        if current_start < current_end:
            gap_minutes = int((current_end - current_start).total_seconds() / 60)
            if gap_minutes >= min_window_minutes:
                # Use first member's id for the combined window label
                result.append(_make_window(
                    "family",
                    current_start.date(),
                    current_start,
                    current_end,
                ))

    return result


def _make_window(
    member_id: str,
    day: date,
    start: datetime,
    end: datetime,
) -> AvailabilityWindow:
    duration = int((end - start).total_seconds() / 60)
    return AvailabilityWindow(
        member_id=member_id,
        member_name=member_id,   # Name is not on CalendarEvent; caller can enrich
        date=day.isoformat(),
        start_time=start,
        end_time=end,
        duration_minutes=duration,
    )
