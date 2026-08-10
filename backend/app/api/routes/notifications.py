"""
Notifications API route — Phase 6.

GET /api/notifications?limit=20

Returns all undelivered notifications for the family, sorted newest first.
Marks returned notifications as delivered=true in the same request.

Security:
- JWT required (get_current_user dependency).
- family_id from JWT only — never from request body or query params.
- family_id scoping enforced at application layer; RLS adds DB-layer enforcement.
- SUPABASE_SERVICE_ROLE_KEY is NOT used here — reads via admin client but
  scoped to family_id before any mark-delivered operations.

See plan: plans/phase-6-proactive-intelligence.md § GET /api/notifications
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.middleware.auth import get_current_user
from app.db.supabase import get_supabase_admin

UTC = timezone.utc
router = APIRouter(prefix="/api")


class NotificationItem(BaseModel):
    id: str
    type: str
    content: str
    trigger_date: str
    created_at: str


class NotificationsResponse(BaseModel):
    pending: list[NotificationItem]
    count: int


def _require_family(user: dict) -> str:
    fid = user.get("family_id")
    if not fid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family not configured for this account.",
        )
    return fid


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> NotificationsResponse:
    """
    Return all pending (undelivered) notifications for the family.

    - Sorted newest first (by created_at).
    - Marks ALL returned notifications as delivered=true.
    - family_id from JWT only.
    - limit: 1-100, default 20.
    """
    family_id = _require_family(user)
    db_admin = get_supabase_admin()
    now_iso = datetime.now(UTC).isoformat()

    try:
        result = (
            db_admin.table("notifications")
            .select("id, type, content, trigger_date, created_at")
            .eq("family_id", family_id)
            .eq("delivered", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch notifications.",
        ) from exc

    if not rows:
        return NotificationsResponse(pending=[], count=0)

    # Mark all returned notifications as delivered
    notification_ids = [r["id"] for r in rows]
    try:
        db_admin.table("notifications").update(
            {"delivered": True, "delivered_at": now_iso}
        ).in_("id", notification_ids).execute()
    except Exception:
        # Mark-delivered failure is non-fatal — return notifications anyway
        pass

    items = [
        NotificationItem(
            id=r["id"],
            type=r["type"],
            content=r.get("content", ""),
            trigger_date=r.get("trigger_date", ""),
            created_at=r.get("created_at", ""),
        )
        for r in rows
    ]

    return NotificationsResponse(pending=items, count=len(items))
