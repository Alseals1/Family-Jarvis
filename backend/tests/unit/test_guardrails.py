"""
Tests for the guardrail engine.

Verifies that no-send, no-purchase, BLOCKED intent, and memory-save
confirmation rules are enforced deterministically.
"""

import pytest
from app.agents.contracts import IntentClassification, IntentType
from app.agents.guardrails import GuardrailResult, check_response


def _intent(intent_type: IntentType) -> IntentClassification:
    return IntentClassification(
        intent=intent_type,
        date_range=None,
        member_filter=None,
        reference_type=None,
        confidence="high",
    )


def _check(response: str, intent_type: IntentType = IntentType.GENERAL) -> GuardrailResult:
    return check_response(
        response=response,
        intent=_intent(intent_type),
        verified_names=["Marcus", "Priya"],
        data_sources=["calendar_events"],
    )


def test_clean_response_passes():
    result = _check("Friday looks clear — no events after 6 PM.")
    assert result.passed is True
    assert result.violations == []
    assert result.safe_response == "Friday looks clear — no events after 6 PM."


def test_send_directive_fails():
    result = _check("I'll send your wife a message right now.")
    assert result.passed is False
    assert any("send" in v.lower() for v in result.violations)


def test_i_have_sent_fails():
    result = _check("I've sent an email to the school.")
    assert result.passed is False


def test_draft_language_passes():
    result = _check(
        "Here's a draft message you could send to your wife:\n"
        "'Hey, dinner at 7?'\nJust let me know when you're ready to send it."
    )
    assert result.passed is True


def test_blocked_intent_returns_safe_refusal():
    result = _check("I'll send the text for you.", IntentType.BLOCKED)
    assert result.passed is False
    assert "blocked_intent" in result.violations
    # safe_response should be a non-empty refusal string
    assert result.safe_response is not None
    assert len(result.safe_response) > 0
    # Safe response should mention drafting, not executing
    assert "send" not in result.safe_response.lower() or "won't" in result.safe_response.lower() or "draft" in result.safe_response.lower()


def test_purchase_directive_fails():
    result = _check("I've booked a table at the Italian place for Friday.")
    assert result.passed is False
    assert any("purchase" in v.lower() or "booking" in v.lower() for v in result.violations)


def test_will_book_fails():
    result = _check("I'll reserve a spot at the restaurant for you.")
    assert result.passed is False


def test_memory_save_without_confirmation_fails():
    result = _check(
        "That sounds great — sushi is a wonderful choice.",
        IntentType.MEMORY_SAVE,
    )
    assert result.passed is False
    assert any("confirmation" in v.lower() or "memory" in v.lower() for v in result.violations)


def test_memory_save_with_confirmation_passes():
    result = _check(
        "Got it — I've saved that to memory: \"We like sushi\".",
        IntentType.MEMORY_SAVE,
    )
    assert result.passed is True


def test_memory_save_noted_passes():
    result = _check("Noted — I'll remember that you prefer early dinners.", IntentType.MEMORY_SAVE)
    assert result.passed is True


def test_guardrail_never_raises_on_empty_response():
    result = _check("", IntentType.GENERAL)
    assert isinstance(result, GuardrailResult)


def test_blocked_intent_regardless_of_response_content():
    # BLOCKED intent always fails, even if response text looks innocent
    result = _check("Happy to help!", IntentType.BLOCKED)
    assert result.passed is False
    assert result.safe_response is not None
