"""
Tests for OrganizerAgent — Phase 5 Task 2.

12 tests covering:
- result shape
- event fetching
- conflict detection is pure Python (no LLM)
- availability is pure Python (no LLM)
- important dates
- briefing summary generation
- LLM skipped when summary not requested
- empty events
- bad date range
- data labeled as untrusted in prompt
- LLM never used for conflict detection
- agent_call recorded in result

All LLM and DB calls are mocked.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

UTC = timezone.utc

FAMILY_ID = "fam-test-organizer"
TASK_ID = "task-org-001"

GOOD_INPUTS = {
    "date_range": {"start": "2026-08-18", "end": "2026-08-24"},
    "members": ["all"],
    "include_summary": False,
    "include_availability": True,
}

BAD_DATE_INPUTS = {
    "date_range": {"start": "not-a-date", "end": "2026-08-24"},
    "members": ["all"],
    "include_summary": False,
    "include_availability": False,
}


def _make_task(inputs: dict | None = None) -> "AgentTask":
    from app.agents.contracts import AgentTask
    return AgentTask(
        task_id=TASK_ID,
        task_type="calendar_query",
        family_id=FAMILY_ID,
        requested_by="manager",
        inputs=inputs or GOOD_INPUTS,
        context={"conversation_turns": 1, "reference_type": None},
        constraints=[],
        timestamp="2026-08-09T10:00:00+00:00",
    )


def _make_llm(response: str = "This week looks manageable.") -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=response)
    llm.complete_structured = AsyncMock(return_value={})
    return llm


def _make_data_fetcher(
    events: list | None = None,
    conflicts: list | None = None,
    availability: list | None = None,
    important_dates: list | None = None,
    family_members: list | None = None,
) -> MagicMock:
    """Return a mocked FamilyDataFetcher."""
    fetcher = MagicMock()
    fetcher.get_calendar_events_and_analysis = AsyncMock(return_value={
        "events": events if events is not None else [
            {"title": "Standup", "member_id": "mem-001", "start": "2026-08-18T09:00:00+00:00",
             "end": "2026-08-18T09:30:00+00:00", "all_day": False, "status": "confirmed"}
        ],
        "conflicts": conflicts if conflicts is not None else [],
        "availability": availability if availability is not None else [],
        "member_ids": ["mem-001"],
    })
    fetcher.get_upcoming_important_dates = AsyncMock(
        return_value=important_dates if important_dates is not None else []
    )
    fetcher.get_family_members = AsyncMock(
        return_value=family_members if family_members is not None else [
            {"id": "mem-001", "name": "Alice", "relationship": "parent"}
        ]
    )
    return fetcher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_organizer_returns_agent_result_shape():
    """Result is an AgentResult with all required fields."""
    from app.agents.organizer import OrganizerAgent
    from app.agents.contracts import AgentResult

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert isinstance(result, AgentResult)
    assert result.agent == "organizer"
    assert result.task_id == TASK_ID
    assert result.task_type == "calendar_query"
    assert isinstance(result.success, bool)
    assert isinstance(result.data, dict)
    assert "events" in result.data
    assert "conflicts" in result.data
    assert "availability" in result.data
    assert "important_dates" in result.data
    assert "briefing_summary" in result.data


@pytest.mark.asyncio
async def test_organizer_fetches_events_for_date_range():
    """get_calendar_events_and_analysis is called with the correct family_id and date range."""
    from app.agents.organizer import OrganizerAgent

    fetcher = _make_data_fetcher()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    fetcher.get_calendar_events_and_analysis.assert_called_once()
    call_args = fetcher.get_calendar_events_and_analysis.call_args
    assert call_args[0][0] == FAMILY_ID or call_args.args[0] == FAMILY_ID


@pytest.mark.asyncio
async def test_organizer_runs_conflict_detection_not_llm():
    """Conflicts come from the data fetcher (pure Python logic), not from LLM."""
    from app.agents.organizer import OrganizerAgent

    conflicts = [
        {
            "member_name": "Alice",
            "event_a": "Meeting",
            "event_b": "Doctor",
            "conflict_time": "2026-08-18T10:00:00+00:00",
            "overlap_minutes": 30,
        }
    ]
    fetcher = _make_data_fetcher(conflicts=conflicts)
    llm = _make_llm()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert result.success is True
    assert result.data["conflicts"] == conflicts
    # LLM complete was NOT called (summary not requested)
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_organizer_calculates_availability_not_llm():
    """Availability windows come from the data fetcher, not LLM."""
    from app.agents.organizer import OrganizerAgent

    availability = [
        {"member_id": "family", "date": "2026-08-20", "start_minute": 1080, "end_minute": 1320}
    ]
    fetcher = _make_data_fetcher(availability=availability)
    llm = _make_llm()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")

    inputs = {**GOOD_INPUTS, "include_availability": True}
    result = await agent.run(_make_task(inputs))

    assert result.data["availability"] == availability
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_organizer_includes_important_dates():
    """Important dates are fetched and included in result data."""
    from app.agents.organizer import OrganizerAgent

    dates = [{"label": "Anniversary", "date": "2026-08-20", "days_until": 2}]
    fetcher = _make_data_fetcher(important_dates=dates)
    agent = OrganizerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task())

    fetcher.get_upcoming_important_dates.assert_called_once()
    assert result.data["important_dates"] == dates


@pytest.mark.asyncio
async def test_organizer_generates_briefing_summary_when_requested():
    """When include_summary=True, LLM.complete is called and result has briefing_summary."""
    from app.agents.organizer import OrganizerAgent

    summary_text = "Alice has a busy Monday. No conflicts this week."
    llm = _make_llm(response=summary_text)
    fetcher = _make_data_fetcher()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")

    inputs = {**GOOD_INPUTS, "include_summary": True}
    result = await agent.run(_make_task(inputs))

    llm.complete.assert_called_once()
    assert result.data["briefing_summary"] == summary_text


@pytest.mark.asyncio
async def test_organizer_skips_llm_when_summary_not_requested():
    """When include_summary=False, LLM is never called."""
    from app.agents.organizer import OrganizerAgent

    llm = _make_llm()
    fetcher = _make_data_fetcher()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")

    inputs = {**GOOD_INPUTS, "include_summary": False}
    result = await agent.run(_make_task(inputs))

    llm.complete.assert_not_called()
    assert result.data["briefing_summary"] is None


@pytest.mark.asyncio
async def test_organizer_returns_empty_events_gracefully():
    """Empty event list results in success=True with empty events/conflicts."""
    from app.agents.organizer import OrganizerAgent

    fetcher = _make_data_fetcher(events=[], conflicts=[])
    agent = OrganizerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task())

    assert result.success is True
    assert result.data["events"] == []
    assert result.data["conflicts"] == []


@pytest.mark.asyncio
async def test_organizer_returns_failure_on_bad_date_range():
    """Malformed date_range causes success=False with a warning, no exception raised."""
    from app.agents.organizer import OrganizerAgent

    fetcher = _make_data_fetcher()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task(BAD_DATE_INPUTS))

    assert result.success is False
    assert any("bad_date_range" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_organizer_data_labeled_as_untrusted_in_prompt():
    """When generating a briefing, the prompt contains [CALENDAR DATA] label."""
    from app.agents.organizer import OrganizerAgent

    captured_messages = []

    async def capture_complete(messages, model, temperature=0.7):
        captured_messages.extend(messages)
        return "Test briefing."

    llm = MagicMock()
    llm.complete = capture_complete

    fetcher = _make_data_fetcher(
        events=[{"title": "Standup", "start": "2026-08-18T09:00:00+00:00"}],
    )
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")

    inputs = {**GOOD_INPUTS, "include_summary": True}
    result = await agent.run(_make_task(inputs))

    # At least one message must contain [CALENDAR DATA]
    all_content = " ".join(m.content for m in captured_messages)
    assert "[CALENDAR DATA]" in all_content
    assert result.data["briefing_summary"] == "Test briefing."


@pytest.mark.asyncio
async def test_organizer_never_invokes_llm_for_conflict_detection():
    """Conflict detection only calls the data fetcher, never the LLM.complete."""
    from app.agents.organizer import OrganizerAgent

    llm = _make_llm()
    fetcher = _make_data_fetcher(
        conflicts=[
            {"member_name": "Bob", "event_a": "A", "event_b": "B",
             "conflict_time": "2026-08-18T11:00:00+00:00", "overlap_minutes": 15}
        ]
    )
    agent = OrganizerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert len(result.data["conflicts"]) == 1
    # LLM complete must NOT be called — conflict detection is pure Python
    llm.complete.assert_not_called()
    llm.complete_structured.assert_not_called()


@pytest.mark.asyncio
async def test_organizer_agent_call_recorded_in_result():
    """result.agent is always 'organizer'."""
    from app.agents.organizer import OrganizerAgent

    fetcher = _make_data_fetcher()
    agent = OrganizerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task())

    assert result.agent == "organizer"
    # data_sources must mention calendar and dates
    assert "calendar_events" in result.data_sources
