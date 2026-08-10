"""
Chat API route for Family JARVIS.

Endpoint:
    POST /api/chat

Security invariants:
    - JWT required — 401 if missing or invalid
    - family_id comes from JWT only — never from request body
    - Empty messages rejected with 422
    - Rate limit: 10 messages per family per minute (in-memory counter)
    - session_id created server-side if not provided
    - Raw calendar event descriptions never appear in responses
      (filtered by FamilyDataFetcher before reaching the route)
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from app.agents.chef import ChefAgent
from app.agents.context import ConversationContextManager
from app.agents.data_fetcher import FamilyDataFetcher
from app.agents.date_planner import DatePlannerAgent
from app.agents.manager import ManagerAgent
from app.agents.organizer import OrganizerAgent
from app.api.middleware.auth import get_current_user
from app.config import get_settings
from app.db.supabase import get_supabase, get_supabase_admin
from app.providers.llm.openrouter import get_llm_provider

UTC = timezone.utc
router = APIRouter(prefix="/api")

# Module-level singletons (one per process)
_context_manager = ConversationContextManager()

# Simple in-memory rate limiter: {family_id: [timestamp, ...]}
_rate_window_seconds = 60
_rate_limit_max = 10
_rate_buckets: dict[str, list[datetime]] = defaultdict(list)


def _check_rate_limit(family_id: str) -> None:
    """Raise 429 if this family has exceeded the rate limit in the current window."""
    now = datetime.now(UTC)
    cutoff = now.timestamp() - _rate_window_seconds
    bucket = _rate_buckets[family_id]
    # Evict old timestamps
    _rate_buckets[family_id] = [ts for ts in bucket if ts.timestamp() > cutoff]
    if len(_rate_buckets[family_id]) >= _rate_limit_max:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before sending another message.",
        )
    _rate_buckets[family_id].append(now)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        return v.strip()


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str
    agent_calls: list[str]
    data_sources: list[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Primary conversation endpoint.

    Accepts a user message and optional session_id. Returns JARVIS's response
    and metadata about what was queried.
    """
    family_id = user.get("family_id")
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family not set up. Please complete onboarding first.",
        )

    _check_rate_limit(family_id)

    session_id = request.session_id or str(uuid.uuid4())

    settings = get_settings()
    _llm = get_llm_provider()
    _db = get_supabase()
    _db_admin = get_supabase_admin()

    _data_fetcher = FamilyDataFetcher(db=_db, db_admin=_db_admin)
    manager = ManagerAgent(
        llm=_llm,
        data_fetcher=_data_fetcher,
        context_manager=_context_manager,
        model=settings.openrouter_model_manager,
        organizer=OrganizerAgent(
            data_fetcher=_data_fetcher,
            llm=_llm,
            model=settings.openrouter_model_organizer,
        ),
        chef=ChefAgent(
            data_fetcher=_data_fetcher,
            llm=_llm,
            model=settings.openrouter_model_chef,
        ),
        date_planner=DatePlannerAgent(
            data_fetcher=_data_fetcher,
            llm=_llm,
            model=settings.openrouter_model_planner,
        ),
    )

    result = await manager.respond(
        message=request.message,
        family_id=family_id,
        session_id=session_id,
    )

    return ChatResponse(
        response=result.response,
        session_id=result.session_id,
        intent=result.intent.value,
        agent_calls=result.agent_calls,
        data_sources=result.data_sources,
    )
