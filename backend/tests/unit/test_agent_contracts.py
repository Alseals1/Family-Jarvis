"""
Tests for agent contract dataclasses and IntentType enum.
"""

import pytest
from app.agents.contracts import (
    AgentResult,
    AgentTask,
    ConversationTurn,
    IntentClassification,
    IntentType,
)


def test_intent_type_values_match_expected_strings():
    assert IntentType.CALENDAR_QUERY.value == "calendar_query"
    assert IntentType.IMPORTANT_DATE.value == "important_date"
    assert IntentType.DINNER_SUGGESTION.value == "dinner_suggestion"
    assert IntentType.DATE_NIGHT.value == "date_night"
    assert IntentType.MEMORY_SAVE.value == "memory_save"
    assert IntentType.GENERAL.value == "general"
    assert IntentType.BLOCKED.value == "blocked"


def test_agent_task_requires_all_fields():
    task = AgentTask(
        task_id="t-001",
        task_type="calendar_query",
        family_id="fam-001",
        requested_by="manager",
        inputs={"date_range": {"start": "2026-08-14", "end": "2026-08-14"}},
        context={"session_id": "sess-001"},
        constraints=["no_cancelled_events"],
        timestamp="2026-08-09T12:00:00Z",
    )
    assert task.task_id == "t-001"
    assert task.family_id == "fam-001"
    assert task.requested_by == "manager"


def test_agent_result_requires_all_fields():
    result = AgentResult(
        task_id="t-001",
        task_type="calendar_query",
        agent="organizer",
        success=True,
        data={"events": []},
        confidence="high",
        data_sources=["calendar_events"],
        warnings=[],
        timestamp="2026-08-09T12:00:01Z",
    )
    assert result.agent == "organizer"
    assert result.success is True
    assert result.confidence == "high"


def test_conversation_turn_defaults_empty_lists():
    turn = ConversationTurn(
        turn_id=1,
        role="user",
        content="What's happening Friday?",
        timestamp="2026-08-09T12:00:00Z",
    )
    assert turn.agent_calls == []
    assert turn.data_sources == []


def test_intent_classification_date_range_nullable():
    classification = IntentClassification(
        intent=IntentType.GENERAL,
        date_range=None,
        member_filter=None,
        reference_type=None,
        confidence="high",
    )
    assert classification.date_range is None
    assert classification.member_filter is None

    with_range = IntentClassification(
        intent=IntentType.CALENDAR_QUERY,
        date_range={"start": "2026-08-14", "end": "2026-08-14"},
        member_filter=["Marcus"],
        reference_type="date",
        confidence="high",
    )
    assert with_range.date_range["start"] == "2026-08-14"
    assert with_range.member_filter == ["Marcus"]
