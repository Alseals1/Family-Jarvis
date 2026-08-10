"""
Notification DB helpers for Phase 6 background jobs.

These helpers use the service-role (admin) client because background jobs run
outside any user request context — there is no JWT to satisfy RLS.

Security rules:
- db_admin (service-role) is used exclusively in job code
- user-facing routes extract family_id from JWT only
- family_id is NEVER accepted from job inputs; jobs query all active families
  from the DB themselves

Schema (supabase/migrations/012_create_notifications.sql):
    id           UUID PK
    family_id    UUID FK families(id)
    type         TEXT  CHECK IN ('birthday','anniversary','trip','conflict',
                                 'briefing','free_evening','dinner_suggestion')
    content      TEXT
    trigger_date DATE
    delivered    BOOLEAN DEFAULT false
    delivered_at TIMESTAMPTZ
    created_at   TIMESTAMPTZ DEFAULT now()
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from supabase import Client

UTC = timezone.utc


class NotificationType(str, Enum):
    """
    Maps logical notification types to the DB CHECK-constraint values.

    morning_briefing and evening_briefing both use the DB value 'briefing'.
    trip_alert → 'trip', conflict_alert → 'conflict'.
    """
    morning_briefing = "briefing"
    evening_briefing = "briefing"
    birthday = "birthday"
    anniversary = "anniversary"
    trip_alert = "trip"
    conflict_alert = "conflict"
    free_evening = "free_evening"
    dinner_suggestion = "dinner_suggestion"


def _db_type(notif_type: NotificationType) -> str:
    """Return the string value accepted by the DB CHECK constraint."""
    return notif_type.value


def insert_notification(
    db_admin: Client,
    family_id: str,
    notif_type: NotificationType,
    title: str,
    body: str,
    trigger_date: date,
) -> dict | None:
    """
    Insert a notification row, deduplicating on (family_id, type, trigger_date).

    Dedup logic: if a row with the same (family_id, type, trigger_date) already
    exists (delivered or not), no insert is performed and None is returned.
    Otherwise the new row is inserted and returned.

    The combined 'content' is stored as "<title>\\n<body>" so callers can
    reconstruct the title and body by splitting on the first newline.

    Args:
        db_admin:     Service-role Supabase client (bypasses RLS).
        family_id:    UUID string of the target family.
        notif_type:   NotificationType enum member.
        title:        Short notification title (single line).
        body:         Notification body text.
        trigger_date: The calendar date this notification fires for.

    Returns:
        The inserted row dict, or None if a duplicate already exists.
    """
    db_type_str = _db_type(notif_type)
    trigger_iso = trigger_date.isoformat() if isinstance(trigger_date, date) else str(trigger_date)

    # Dedup check — same family + type + trigger_date
    existing = (
        db_admin.table("notifications")
        .select("id")
        .eq("family_id", family_id)
        .eq("type", db_type_str)
        .eq("trigger_date", trigger_iso)
        .execute()
    )
    if existing.data:
        return None

    content = f"{title}\n{body}"
    result = (
        db_admin.table("notifications")
        .insert(
            {
                "family_id": family_id,
                "type": db_type_str,
                "content": content,
                "trigger_date": trigger_iso,
                "delivered": False,
            }
        )
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def get_pending_notifications(
    db_admin: Client,
    family_id: str,
) -> list[dict]:
    """
    Return all undelivered notification rows for the family.

    Ordered by trigger_date ascending (soonest first), then created_at.

    Args:
        db_admin:  Service-role Supabase client.
        family_id: UUID string of the target family.

    Returns:
        List of notification row dicts (all columns).
    """
    result = (
        db_admin.table("notifications")
        .select("*")
        .eq("family_id", family_id)
        .eq("delivered", False)
        .order("trigger_date", desc=False)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


def mark_delivered(
    db_admin: Client,
    notification_id: str,
) -> dict | None:
    """
    Set delivered=True and delivered_at=now() on a notification row.

    Args:
        db_admin:        Service-role Supabase client.
        notification_id: UUID string of the notification to mark delivered.

    Returns:
        The updated row dict, or None if the row was not found.
    """
    now_iso = datetime.now(UTC).isoformat()
    result = (
        db_admin.table("notifications")
        .update({"delivered": True, "delivered_at": now_iso})
        .eq("id", notification_id)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None
