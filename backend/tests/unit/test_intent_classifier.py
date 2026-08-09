"""
Tests for the intent classifier.

All LLM calls are mocked — no real OpenRouter calls.
Verifies correct intent classification, date normalization, context resolution,
and graceful fallback on parse failures.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.agents.contracts import ConversationTurn, IntentClassification, IntentType
from app.agents.intent import classify_intent, _parse_result

TS = "2026-08-09T12:00:00Z"


def _turn(role: str, content: str) -> ConversationTurn:
    return ConversationTurn(turn_id=1, role=role, content=content, timestamp=TS)


def _mock_llm(return_value: dict):
    """Return a mock LLMProvider whose complete_structured returns the given dict."""
    mock = AsyncMock()
    mock.complete_structured = AsyncMock(return_value=return_value)
    return mock


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calendar_question_classified_correctly():
    llm = _mock_llm({
        "intent": "calendar_query",
        "date_range": {"start": "2026-08-14", "end": "2026-08-14"},
        "member_filter": None,
        "reference_type": "date",
        "confidence": "high",
    })
    result = await classify_intent("What's happening Friday?", [], llm, "test-model")
    assert result.intent == IntentType.CALENDAR_QUERY
    assert result.date_range is not None
    assert result.confidence == "high"


@pytest.mark.asyncio
async def test_important_date_classified_correctly():
    llm = _mock_llm({
        "intent": "important_date",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    result = await classify_intent("When is our anniversary?", [], llm, "test-model")
    assert result.intent == IntentType.IMPORTANT_DATE


@pytest.mark.asyncio
async def test_dinner_request_classified_correctly():
    llm = _mock_llm({
        "intent": "dinner_suggestion",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    result = await classify_intent("What should we make for dinner?", [], llm, "test-model")
    assert result.intent == IntentType.DINNER_SUGGESTION


@pytest.mark.asyncio
async def test_date_night_classified_correctly():
    llm = _mock_llm({
        "intent": "date_night",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    result = await classify_intent("When can we have a date night?", [], llm, "test-model")
    assert result.intent == IntentType.DATE_NIGHT


@pytest.mark.asyncio
async def test_memory_save_classified_correctly():
    llm = _mock_llm({
        "intent": "memory_save",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    result = await classify_intent("Remember that we like sushi", [], llm, "test-model")
    assert result.intent == IntentType.MEMORY_SAVE


@pytest.mark.asyncio
async def test_no_send_request_classified_as_blocked():
    llm = _mock_llm({
        "intent": "blocked",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    result = await classify_intent("Send my wife a text saying hi", [], llm, "test-model")
    assert result.intent == IntentType.BLOCKED


@pytest.mark.asyncio
async def test_follow_up_uses_context():
    # After asking about Friday, "what about Saturday?" should resolve to Saturday
    context = [
        _turn("user", "What's happening Friday?"),
        _turn("assistant", "Friday looks clear."),
    ]
    llm = _mock_llm({
        "intent": "calendar_query",
        "date_range": {"start": "2026-08-15", "end": "2026-08-15"},
        "member_filter": None,
        "reference_type": "follow_up",
        "confidence": "high",
    })
    result = await classify_intent("What about Saturday?", context, llm, "test-model")
    assert result.intent == IntentType.CALENDAR_QUERY
    assert result.reference_type == "follow_up"
    assert result.date_range == {"start": "2026-08-15", "end": "2026-08-15"}

    # Verify context was passed to LLM
    call_args = llm.complete_structured.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]
    message_contents = [m.content for m in messages]
    assert any("Friday" in c for c in message_contents)


@pytest.mark.asyncio
async def test_parse_failure_falls_back_to_general():
    llm = AsyncMock()
    llm.complete_structured = AsyncMock(side_effect=ValueError("bad json"))
    result = await classify_intent("Some message", [], llm, "test-model")
    assert result.intent == IntentType.GENERAL
    assert result.confidence == "low"


@pytest.mark.asyncio
async def test_date_normalization_friday():
    # The LLM returns an absolute date — verify the date_range is preserved correctly
    friday = "2026-08-14"
    llm = _mock_llm({
        "intent": "calendar_query",
        "date_range": {"start": friday, "end": friday},
        "member_filter": None,
        "reference_type": "date",
        "confidence": "high",
    })
    result = await classify_intent("What's on Friday?", [], llm, "test-model")
    assert result.date_range["start"] == friday
    assert result.date_range["end"] == friday


@pytest.mark.asyncio
async def test_incomplete_date_range_nulled_out():
    # If LLM returns date_range with only start and no end, it should be None
    llm = _mock_llm({
        "intent": "calendar_query",
        "date_range": {"start": "2026-08-14"},   # missing "end"
        "member_filter": None,
        "reference_type": None,
        "confidence": "medium",
    })
    result = await classify_intent("What about Friday?", [], llm, "test-model")
    assert result.date_range is None


# ---------------------------------------------------------------------------
# _parse_result unit tests (no LLM needed)
# ---------------------------------------------------------------------------

def test_parse_result_unknown_intent_falls_back_to_general():
    result = _parse_result({"intent": "totally_unknown", "confidence": "high"})
    assert result.intent == IntentType.GENERAL


def test_parse_result_invalid_confidence_defaults_to_low():
    result = _parse_result({"intent": "general", "confidence": "very_high"})
    assert result.confidence == "low"


def test_parse_result_invalid_reference_type_nulled():
    result = _parse_result({
        "intent": "calendar_query",
        "confidence": "high",
        "reference_type": "nonsense",
    })
    assert result.reference_type is None
