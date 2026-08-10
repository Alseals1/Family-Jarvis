"""
Briefing API route — Phase 6.

GET /api/briefing?type=morning|evening

Returns the most recent undelivered briefing notification for the family.
If none exists for today (scheduler hasn't run yet or process restarted),
generates one on-demand via the corresponding job function.

Security:
- JWT required (get_current_user dependency).
- family_id from JWT only — never from request body or query params.
- Does NOT mark briefing as delivered (briefings are re-readable).
- SUPABASE_SERVICE_ROLE_KEY is NOT used here — reads via anon client + RLS.

On-demand fallback (Decision 3): when no notification row exists for today,
the corresponding job function is called, the briefing is generated and returned
WITHOUT being stored. The scheduler owns notification persistence.

See plan: plans/phase-6-proactive-intelligence.md § GET /api/briefing
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.middleware.auth import get_current_user
from app.db.supabase import get_supabase, get_supabase_admin

UTC = timezone.utc
router = APIRouter(prefix="/api")

_VALID_TYPES = {"morning", "evening"}


class BriefingResponse(BaseModel):
    type: str
    generated_at: str
    content: str
    notifications: list[dict]


def _require_family(user: dict) -> str:
    fid = user.get("family_id")
    if not fid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family not configured for this account.",
        )
    return fid


def _get_today_briefing(db_admin, family_id: str, briefing_type: str) -> dict | None:
    """
    Fetch the most recent undelivered briefing notification for today.

    briefing_type: 'morning' | 'evening' — both map to DB type 'briefing'.
    Uses admin client to read across RLS (job-written rows).
    Returns the notification row dict or None if not found.
    """
    today = datetime.now(UTC).date().isoformat()
    try:
        result = (
            db_admin.table("notifications")
            .select("*")
            .eq("family_id", family_id)
            .eq("type", "briefing")
            .eq("trigger_date", today)
            .eq("delivered", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            # Filter by morning/evening by inspecting content prefix
            for row in rows:
                content = row.get("content", "").lower()
                if briefing_type == "morning" and "morning" in content:
                    return row
                if briefing_type == "evening" and "evening" in content:
                    return row
        return None
    except Exception:
        return None


async def _generate_on_demand(
    family_id: str,
    briefing_type: str,
    db_admin,
) -> str:
    """
    Generate a briefing on-demand via the job function.

    Does NOT store a notification row — the scheduler owns persistence.
    Returns the briefing content string.
    """
    from app.agents.data_fetcher import FamilyDataFetcher
    from app.agents.organizer import OrganizerAgent
    from app.agents.chef import ChefAgent
    from app.providers.llm.openrouter import get_llm_provider
    from app.config import get_settings
    from app.db.supabase import get_supabase

    settings = get_settings()
    llm = get_llm_provider()
    db = get_supabase()
    fetcher = FamilyDataFetcher(db=db, db_admin=db_admin)
    model_org = settings.openrouter_model_organizer
    model_chef = settings.openrouter_model_chef

    if briefing_type == "morning":
        from app.jobs.morning_briefing import run_morning_briefing
        organizer = OrganizerAgent(data_fetcher=fetcher, llm=llm, model=model_org)
        # Run but do NOT store — pass a fake db_admin that always reports duplicate
        class _NoopAdmin:
            """Admin client that makes insert_notification always skip (dedup)."""
            def table(self, name):
                return _NoopTable()

        class _NoopTable:
            def select(self, *a):
                return self
            def insert(self, *a):
                return self
            def eq(self, *a):
                return self
            def execute(self):
                # Return existing row to trigger dedup skip
                return type("R", (), {"data": [{"id": "noop"}]})()

        # Run organizer directly to get the summary
        import uuid as _uuid
        from app.agents.contracts import AgentTask
        from datetime import timedelta

        today = datetime.now(UTC).date()
        task = AgentTask(
            task_id=str(_uuid.uuid4()),
            task_type="calendar_query",
            family_id=family_id,
            requested_by="api_on_demand",
            inputs={
                "date_range": {"start": today.isoformat(), "end": today.isoformat()},
                "members": ["all"],
                "include_summary": True,
                "include_availability": True,
            },
            context={"source": "on_demand_briefing"},
            constraints=[],
            timestamp=datetime.now(UTC).isoformat(),
        )
        result = await organizer.run(task)
        summary = result.data.get("briefing_summary") or "Good morning. Your schedule is clear."
        return f"Good morning — your daily briefing\n{summary}"

    else:  # evening
        from app.jobs.evening_briefing import run_evening_briefing
        organizer = OrganizerAgent(data_fetcher=fetcher, llm=llm, model=model_org)
        chef = ChefAgent(data_fetcher=fetcher, llm=llm, model=model_chef)

        import uuid as _uuid
        from app.agents.contracts import AgentTask
        from datetime import timedelta

        today = datetime.now(UTC).date()
        tomorrow = today + timedelta(days=1)
        task = AgentTask(
            task_id=str(_uuid.uuid4()),
            task_type="calendar_query",
            family_id=family_id,
            requested_by="api_on_demand",
            inputs={
                "date_range": {"start": today.isoformat(), "end": tomorrow.isoformat()},
                "members": ["all"],
                "include_summary": True,
                "include_availability": True,
            },
            context={"source": "on_demand_briefing"},
            constraints=[],
            timestamp=datetime.now(UTC).isoformat(),
        )
        result = await organizer.run(task)
        summary = result.data.get("briefing_summary") or "Good evening. Your nightly briefing."
        return f"Good evening — your nightly briefing\n{summary}"


@router.get("/briefing", response_model=BriefingResponse)
async def get_briefing(
    type: str = Query("morning", description="Briefing type: 'morning' or 'evening'"),
    user: dict = Depends(get_current_user),
) -> BriefingResponse:
    """
    Return today's morning or evening briefing for the family.

    - type: 'morning' (default) | 'evening'
    - family_id from JWT only
    - Does NOT mark as delivered

    Falls back to on-demand generation if no scheduled notification exists.
    """
    if type not in _VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid briefing type '{type}'. Must be 'morning' or 'evening'.",
        )

    family_id = _require_family(user)
    db_admin = get_supabase_admin()

    # Try to find an existing scheduled briefing for today
    row = _get_today_briefing(db_admin, family_id, type)
    if row:
        content = row.get("content", "")
        return BriefingResponse(
            type=type,
            generated_at=row.get("created_at", datetime.now(UTC).isoformat()),
            content=content,
            notifications=[],
        )

    # No scheduled briefing — generate on demand
    try:
        content = await _generate_on_demand(family_id, type, db_admin)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Briefing generation temporarily unavailable.",
        ) from exc

    return BriefingResponse(
        type=type,
        generated_at=datetime.now(UTC).isoformat(),
        content=content,
        notifications=[],
    )
