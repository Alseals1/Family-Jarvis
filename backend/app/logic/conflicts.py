"""
Conflict detection for Family JARVIS.

A conflict is defined as: a single family member having two events whose
time intervals overlap simultaneously (they cannot be in two places at once).

Rules:
- All-day events do NOT conflict with time-bounded events
- Cancelled events are excluded entirely
- Duplicate external_ids are deduplicated before detection
- Different family members having overlapping events is NOT a conflict —
  it is a scheduling awareness item for the Organizer Agent

This module is pure Python — no LLM, no DB, no HTTP.
"""

from __future__ import annotations

from datetime import datetime

from app.providers.calendar.base import CalendarEvent
from app.models.calendar import CalendarConflict
from app.logic.dates import intervals_overlap


def detect_conflicts(events: list[CalendarEvent]) -> list[CalendarConflict]:
    """
    Given a flat list of CalendarEvent objects (for any number of family
    members, already filtered to a time window), return every conflicting pair.

    Returns an empty list if no conflicts are found.
    """
    # Step 1: Deduplicate by external_id (keep first occurrence)
    seen_ids: set[str] = set()
    deduped: list[CalendarEvent] = []
    for event in events:
        if event.external_id not in seen_ids:
            seen_ids.add(event.external_id)
            deduped.append(event)

    # Step 2: Exclude cancelled and all-day events from conflict consideration
    eligible: list[CalendarEvent] = [
        e for e in deduped
        if e.status != "cancelled" and not e.all_day
    ]

    # Step 3: Group by family_member_id
    by_member: dict[str, list[CalendarEvent]] = {}
    for event in eligible:
        by_member.setdefault(event.family_member_id, []).append(event)

    # Step 4: For each member, check all pairs for overlap
    conflicts: list[CalendarConflict] = []
    for member_id, member_events in by_member.items():
        n = len(member_events)
        for i in range(n):
            for j in range(i + 1, n):
                a = member_events[i]
                b = member_events[j]
                if intervals_overlap(a.start_time, a.end_time,
                                     b.start_time, b.end_time):
                    overlap_start = max(a.start_time, b.start_time)
                    overlap_end = min(a.end_time, b.end_time)
                    overlap_minutes = int(
                        (overlap_end - overlap_start).total_seconds() / 60
                    )
                    conflicts.append(
                        CalendarConflict(
                            conflict_time=overlap_start,
                            member_id=member_id,
                            member_name=a.family_member_id,  # name not on event; use id
                            event_a_title=a.title,
                            event_b_title=b.title,
                            overlap_minutes=overlap_minutes,
                        )
                    )

    return conflicts
