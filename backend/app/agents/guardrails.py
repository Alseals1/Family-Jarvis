"""
Guardrail engine for Family JARVIS.

Post-generation checks applied before any response reaches the user.
Enforces the no-invention, no-send, and BLOCKED intent rules deterministically.

These checks are rule-based — they never call an LLM and never raise.

Note: The LLM system prompt's no-invention instruction is the primary defense
against invented entities. The guardrail engine handles checks that are
100% deterministic: no-send rule, BLOCKED intent safe refusals, and
memory-save confirmation enforcement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.contracts import IntentClassification, IntentType

# Phrases that indicate JARVIS is directing an action to send/contact/book.
# Draft language ("here's a message you could send") is allowed —
# only first-person action directives are blocked.
_SEND_ACTION_PATTERNS = [
    r"\bI(?:'ll| will| can| am going to)\s+(?:send|email|text|message|call|contact|book|reserve|purchase|buy|order)\b",
    r"\bI(?:'ve| have)\s+(?:sent|emailed|texted|messaged|called|booked|reserved|purchased|bought|ordered)\b",
    r"\bSending\s+(?:an?\s+)?(?:email|text|message)\b",
]

_SEND_ACTION_RE = re.compile(
    "|".join(_SEND_ACTION_PATTERNS),
    re.IGNORECASE,
)

_PURCHASE_ACTION_PATTERNS = [
    r"\bI(?:'ll| will| have| am going to)\s+(?:book|reserve|purchase|buy|order)\b",
    r"\bI(?:'ve| have)\s+(?:booked|reserved|purchased|bought|ordered)\b",
]

_PURCHASE_ACTION_RE = re.compile(
    "|".join(_PURCHASE_ACTION_PATTERNS),
    re.IGNORECASE,
)

# Safe refusal for BLOCKED intents
_BLOCKED_REFUSALS = {
    "send": "I can draft that message for you, but I won't send anything directly. Would you like me to write a draft?",
    "purchase": "I don't make purchases or reservations — I can recommend options, but you'll need to book it yourself.",
    "default": "I'm not able to do that directly, but I can help you think through it.",
}


@dataclass
class GuardrailResult:
    passed: bool
    violations: list[str]
    safe_response: str | None   # set if passed=True; None if failed


def _detect_send_violation(response: str) -> str | None:
    """Return a violation description if the response directs a send action."""
    match = _SEND_ACTION_RE.search(response)
    if match:
        return f"Response contains a send/contact action directive: '{match.group()}'"
    return None


def _detect_purchase_violation(response: str) -> str | None:
    """Return a violation description if the response directs a purchase action."""
    match = _PURCHASE_ACTION_RE.search(response)
    if match:
        return f"Response contains a purchase/booking action directive: '{match.group()}'"
    return None


def _memory_confirmation_present(response: str) -> bool:
    """Return True if the response contains a memory-save confirmation phrase."""
    lower = response.lower()
    return any(
        phrase in lower
        for phrase in [
            "i've saved",
            "i have saved",
            "saved that",
            "saved to memory",
            "got it",
            "noted",
            "i'll remember",
            "i will remember",
            "remembered",
        ]
    )


def check_response(
    response: str,
    intent: IntentClassification,
    verified_names: list[str],
    data_sources: list[str],
) -> GuardrailResult:
    """
    Check a candidate response before it reaches the user.

    Checks:
    1. BLOCKED intent → return safe refusal without passing the original response
    2. No-send rule → response must not direct JARVIS to send messages/emails/texts
    3. No-purchase rule → response must not direct JARVIS to book/buy/order
    4. MEMORY_SAVE intent → response must include a confirmation phrase

    Never raises. Returns GuardrailResult.
    """
    # BLOCKED intent: replace with a safe refusal, don't expose the response
    if intent.intent == IntentType.BLOCKED:
        # Determine what kind of blocked action to tailor the refusal
        lower = response.lower() if response else ""
        if any(word in lower for word in ["send", "email", "text", "message"]):
            safe = _BLOCKED_REFUSALS["send"]
        elif any(word in lower for word in ["book", "reserve", "purchase", "buy", "order"]):
            safe = _BLOCKED_REFUSALS["purchase"]
        else:
            safe = _BLOCKED_REFUSALS["default"]
        return GuardrailResult(passed=False, violations=["blocked_intent"], safe_response=safe)

    violations: list[str] = []

    send_violation = _detect_send_violation(response)
    if send_violation:
        violations.append(send_violation)

    purchase_violation = _detect_purchase_violation(response)
    if purchase_violation:
        violations.append(purchase_violation)

    if intent.intent == IntentType.MEMORY_SAVE and not _memory_confirmation_present(response):
        violations.append("Memory save intent but no confirmation phrase in response")

    if violations:
        return GuardrailResult(passed=False, violations=violations, safe_response=None)

    return GuardrailResult(passed=True, violations=[], safe_response=response)
