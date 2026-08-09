"""
Intent classifier for Family JARVIS.

Classifies a user message into a structured IntentClassification using the
LLM with structured output. Conversation context (last few turns) is included
so that follow-ups like "what about Saturday?" resolve correctly.

Design notes:
- System prompt is short and focused — saves tokens vs full JARVIS persona
- Date references are normalized to absolute ISO dates
- Falls back to GENERAL intent on any parse failure — never raises
- BLOCKED intent is returned for no-send and no-purchase requests
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.agents.contracts import ConversationTurn, IntentClassification, IntentType
from app.providers.llm.base import LLMProvider, Message

_INTENT_SCHEMA = {
    "type": "object",
    "required": ["intent", "confidence"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": [t.value for t in IntentType],
        },
        "date_range": {
            "type": ["object", "null"],
            "properties": {
                "start": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            },
        },
        "member_filter": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "reference_type": {
            "type": ["string", "null"],
            "enum": ["follow_up", "date", "person", None],
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
    },
}

_FALLBACK = IntentClassification(
    intent=IntentType.GENERAL,
    date_range=None,
    member_filter=None,
    reference_type=None,
    confidence="low",
)


def _today_str() -> str:
    return date.today().isoformat()


def _build_system_prompt(today: str) -> str:
    return f"""You are an intent classifier for a family assistant app. Today's date is {today}.

Classify the user message into one of these intents:
- calendar_query: asking about events, schedule, conflicts, or availability on specific dates
- important_date: asking about birthdays, anniversaries, or other important family dates
- dinner_suggestion: asking what to cook or eat for dinner
- date_night: asking about date night ideas, when to have a date, romantic planning
- memory_save: asking the assistant to remember or note something
- general: any other question or conversation
- blocked: request to send a message/email/text, make a purchase, or book/reserve something

Date resolution rules (relative to today {today}):
- "today" → {today}
- "tomorrow" → {(date.fromisoformat(today) + timedelta(days=1)).isoformat()}
- "this weekend" → next Saturday/Sunday
- "Friday" → the upcoming Friday
- Always output absolute ISO dates (YYYY-MM-DD), not relative references

Return ONLY valid JSON matching the schema. No explanation."""


def _context_to_messages(context: list[ConversationTurn]) -> list[Message]:
    """Convert the last 3 turns of context to LLM messages for reference resolution."""
    recent = context[-3:] if len(context) > 3 else context
    return [Message(role=t.role, content=t.content) for t in recent]


def _parse_result(raw: dict) -> IntentClassification:
    intent_str = raw.get("intent", "general")
    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.GENERAL

    date_range = raw.get("date_range")
    if date_range and not (date_range.get("start") and date_range.get("end")):
        date_range = None

    reference_type = raw.get("reference_type")
    if reference_type not in ("follow_up", "date", "person", None):
        reference_type = None

    confidence = raw.get("confidence", "low")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    return IntentClassification(
        intent=intent,
        date_range=date_range,
        member_filter=raw.get("member_filter"),
        reference_type=reference_type,
        confidence=confidence,
    )


async def classify_intent(
    message: str,
    context: list[ConversationTurn],
    llm: LLMProvider,
    model: str,
) -> IntentClassification:
    """
    Classify a user message into a structured IntentClassification.

    Uses LLM with structured output. Includes the last 3 turns of context
    so follow-ups resolve correctly. Falls back to GENERAL on any failure.
    """
    today = _today_str()
    system_msg = Message(role="system", content=_build_system_prompt(today))
    context_messages = _context_to_messages(context)
    user_msg = Message(role="user", content=message)

    messages = [system_msg] + context_messages + [user_msg]

    try:
        raw = await llm.complete_structured(
            messages=messages,
            schema=_INTENT_SCHEMA,
            model=model,
        )
        return _parse_result(raw)
    except Exception:
        return _FALLBACK
