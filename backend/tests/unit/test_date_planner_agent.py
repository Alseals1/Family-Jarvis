"""
Tests for DatePlannerAgent — Phase 5 Task 4.

14 tests covering:
- result shape
- date history fetched
- dining preferences fetched
- activity preferences fetched
- availability windows from task.inputs
- no availability → no LLM call
- LLM skipped when no windows
- calls complete_structured
- never_books always True
- recent activities in prompt
- failure on LLM error
- data_sources recorded
- recommendation includes date and activity
- alternatives capped at 2

All LLM and DB calls are mocked.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

UTC = timezone.utc

FAMILY_ID = "fam-test-planner"
TASK_ID = "task-dp-001"

WINDOWS = [
    {
        "date": "2026-08-22",
        "start_time": "2026-08-22T18:00:00+00:00",
        "end_time": "2026-08-22T22:00:00+00:00",
        "duration_minutes": 240,
    },
    {
        "date": "2026-08-25",
        "start_time": "2026-08-25T19:00:00+00:00",
        "end_time": "2026-08-25T23:00:00+00:00",
        "duration_minutes": 240,
    },
]

LLM_DP_RESPONSE = {
    "recommendation": {
        "date": "2026-08-22",
        "time_window": "7:00 PM - 10:00 PM",
        "activity": "Italian dinner",
        "reason": "You haven't had Italian in three weeks.",
        "alternatives": [
            {"date": "2026-08-25", "activity": "Jazz bar"},
        ],
    },
    "never_books": True,
}


def _make_task(inputs: dict | None = None) -> "AgentTask":
    from app.agents.contracts import AgentTask
    return AgentTask(
        task_id=TASK_ID,
        task_type="date_night",
        family_id=FAMILY_ID,
        requested_by="manager",
        inputs=inputs if inputs is not None else {
            "availability_windows": WINDOWS,
            "look_ahead_days": 30,
        },
        context={"conversation_turns": 1, "reference_type": None},
        constraints=[],
        timestamp="2026-08-09T10:00:00+00:00",
    )


def _make_llm(structured_response: dict | None = None, raise_error: bool = False) -> MagicMock:
    llm = MagicMock()
    if raise_error:
        llm.complete_structured = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    else:
        llm.complete_structured = AsyncMock(
            return_value=structured_response if structured_response is not None else LLM_DP_RESPONSE
        )
    llm.complete = AsyncMock(return_value="")
    return llm


def _make_data_fetcher(
    date_history: list | None = None,
    dining_prefs: dict | None = None,
    activity_prefs: dict | None = None,
) -> MagicMock:
    fetcher = MagicMock()
    fetcher.get_date_history = AsyncMock(
        return_value=date_history if date_history is not None else [
            {"date": "2026-07-28", "activity": "dinner at Carmine's", "restaurant": "Carmine's Italian", "notes": None, "rating": 5}
        ]
    )
    _dining = dining_prefs if dining_prefs is not None else {"budget": "medium", "cuisine": "Italian"}
    _activity = activity_prefs if activity_prefs is not None else {"type": "dinner and a show"}

    async def _get_prefs(family_id, category):
        if category == "dining":
            return _dining
        return _activity

    fetcher.get_family_preferences = AsyncMock(side_effect=_get_prefs)
    return fetcher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_date_planner_returns_agent_result_shape():
    """Result is an AgentResult with all required fields."""
    from app.agents.date_planner import DatePlannerAgent
    from app.agents.contracts import AgentResult

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert isinstance(result, AgentResult)
    assert result.agent == "date_planner"
    assert result.task_id == TASK_ID
    assert isinstance(result.data, dict)
    assert "recommendation" in result.data
    assert "never_books" in result.data


@pytest.mark.asyncio
async def test_date_planner_fetches_date_history():
    """get_date_history is called with the correct family_id."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    fetcher.get_date_history.assert_called_once_with(FAMILY_ID)


@pytest.mark.asyncio
async def test_date_planner_fetches_dining_preferences():
    """get_family_preferences is called with category='dining'."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    # Check that dining preferences were fetched
    calls = fetcher.get_family_preferences.call_args_list
    categories = [c.args[1] if c.args else c.kwargs.get("category") for c in calls]
    assert "dining" in categories


@pytest.mark.asyncio
async def test_date_planner_fetches_activity_preferences():
    """get_family_preferences is called with category='activities'."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    calls = fetcher.get_family_preferences.call_args_list
    categories = [c.args[1] if c.args else c.kwargs.get("category") for c in calls]
    assert "activities" in categories


@pytest.mark.asyncio
async def test_date_planner_uses_availability_windows_from_task():
    """Availability windows come from task.inputs, not fetched by the agent."""
    from app.agents.date_planner import DatePlannerAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_DP_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    # Window dates must appear in the prompt
    assert "2026-08-22" in system_content


@pytest.mark.asyncio
async def test_date_planner_returns_no_availability_when_windows_empty():
    """Empty availability_windows returns no-availability result with date=None."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task({"availability_windows": [], "look_ahead_days": 30}))

    assert result.success is True
    assert result.data["recommendation"]["date"] is None
    assert "no_availability_windows" in result.warnings
    assert result.data["never_books"] is True


@pytest.mark.asyncio
async def test_date_planner_skips_llm_when_no_windows():
    """When no windows are available, LLM is never called."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task({"availability_windows": [], "look_ahead_days": 30}))

    llm.complete_structured.assert_not_called()


@pytest.mark.asyncio
async def test_date_planner_calls_complete_structured():
    """complete_structured is called with DATE_PLANNER_OUTPUT_SCHEMA when windows exist."""
    from app.agents.date_planner import DatePlannerAgent, DATE_PLANNER_OUTPUT_SCHEMA

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    llm.complete_structured.assert_called_once()
    call_kwargs = llm.complete_structured.call_args
    schema_arg = call_kwargs.kwargs.get("schema") or call_kwargs.args[1]
    assert schema_arg == DATE_PLANNER_OUTPUT_SCHEMA


@pytest.mark.asyncio
async def test_date_planner_result_always_has_never_books_true():
    """never_books is True in all result paths — success and no-availability."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()

    # Success path
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result_success = await agent.run(_make_task())
    assert result_success.data["never_books"] is True

    # No availability path
    result_no_avail = await agent.run(_make_task({"availability_windows": [], "look_ahead_days": 30}))
    assert result_no_avail.data["never_books"] is True


@pytest.mark.asyncio
async def test_date_planner_avoids_recent_activities_in_prompt():
    """Date history (past activities/restaurants) appears in the prompt."""
    from app.agents.date_planner import DatePlannerAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_DP_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    history = [
        {"date": "2026-07-28", "activity": "Jazz concert", "restaurant": None, "notes": None, "rating": 5}
    ]
    fetcher = _make_data_fetcher(date_history=history)
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    assert "Jazz concert" in system_content


@pytest.mark.asyncio
async def test_date_planner_returns_failure_on_llm_error():
    """LLM error results in success=False with warning, never_books still True."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm(raise_error=True)
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert result.success is False
    assert any("llm_error" in w for w in result.warnings)
    # never_books must still be True even on failure
    assert result.data["never_books"] is True


@pytest.mark.asyncio
async def test_date_planner_result_data_sources_recorded():
    """result.data_sources includes date_history and preferences."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task())

    assert "date_history" in result.data_sources
    assert "preferences" in result.data_sources


@pytest.mark.asyncio
async def test_date_planner_recommendation_includes_date_and_activity():
    """recommendation contains date and activity fields from LLM response."""
    from app.agents.date_planner import DatePlannerAgent

    fetcher = _make_data_fetcher()
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    result = await agent.run(_make_task())

    rec = result.data["recommendation"]
    assert rec.get("date") == "2026-08-22"
    assert rec.get("activity") == "Italian dinner"


@pytest.mark.asyncio
async def test_date_planner_alternatives_max_two():
    """Alternatives list is capped at 2 even if LLM returns more."""
    from app.agents.date_planner import DatePlannerAgent

    too_many_alternatives = {
        "recommendation": {
            "date": "2026-08-22",
            "time_window": "7:00 PM - 10:00 PM",
            "activity": "Italian dinner",
            "reason": "Good choice.",
            "alternatives": [
                {"date": "2026-08-23", "activity": "Movie"},
                {"date": "2026-08-24", "activity": "Concert"},
                {"date": "2026-08-25", "activity": "Bowling"},  # should be truncated
            ],
        },
        "never_books": True,
    }

    fetcher = _make_data_fetcher()
    llm = _make_llm(structured_response=too_many_alternatives)
    agent = DatePlannerAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert len(result.data["recommendation"]["alternatives"]) <= 2
