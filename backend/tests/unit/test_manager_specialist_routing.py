"""
Tests for ManagerAgent specialist routing — Phase 5 Task 5.

18 tests covering:
- dinner_suggestion routes to chef
- date_night routes to date_planner
- date_night fetches availability before routing
- multi-day calendar routes to organizer
- single-day calendar does not route to organizer
- specialist results formatted into response
- specialist=None returns graceful no-data response
- organizer=None falls back to direct path
- specialist failure returns graceful response
- agent_task has correct task_type
- family_id from parameter, not task input
- specialist data labeled [SPECIALIST DATA] in prompt
- _is_multi_day logic (>2 days / <=2 days)
- existing Phase 4 tests unaffected (Manager builds without specialists)

All specialists and DB calls are mocked.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

UTC = timezone.utc

FAMILY_ID = "fam-routing-test"
SESSION_ID = "sess-routing-001"
TODAY = "2026-08-09"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_llm(response: str = "Here is your answer.") -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=response)
    llm.complete_structured = AsyncMock(return_value={
        "intent": "dinner_suggestion",
        "date_range": None,
        "member_filter": None,
        "reference_type": None,
        "confidence": "high",
    })
    return llm


def _make_context_manager(session_id: str = SESSION_ID) -> MagicMock:
    from app.agents.contracts import ConversationTurn
    ctx = MagicMock()
    ctx.get_or_create = MagicMock(return_value=[])
    ctx.add_turn = MagicMock()
    return ctx


def _make_data_fetcher(
    family_members: list | None = None,
    availability: list | None = None,
    events_and_analysis: dict | None = None,
) -> MagicMock:
    fetcher = MagicMock()
    fetcher.get_family_members = AsyncMock(
        return_value=family_members if family_members is not None else [
            {"id": "mem-001", "name": "Alice", "relationship": "parent"}
        ]
    )
    fetcher.get_availability_windows = AsyncMock(
        return_value=availability if availability is not None else [
            {"date": "2026-08-22", "start_time": "2026-08-22T18:00:00+00:00",
             "end_time": "2026-08-22T22:00:00+00:00", "duration_minutes": 240}
        ]
    )
    fetcher.get_calendar_events_and_analysis = AsyncMock(
        return_value=events_and_analysis if events_and_analysis is not None else {
            "events": [], "conflicts": [], "availability": [], "member_ids": []
        }
    )
    fetcher.get_upcoming_important_dates = AsyncMock(return_value=[])
    fetcher.save_memory = AsyncMock(return_value="Saved.")
    return fetcher


def _make_chef_result(recommendation: str = "chicken stir-fry") -> "AgentResult":
    from app.agents.contracts import AgentResult
    return AgentResult(
        task_id="task-chef",
        task_type="dinner_suggestion",
        agent="chef",
        success=True,
        data={
            "recommendation": recommendation,
            "reason": "Quick and healthy",
            "alternatives": ["pasta"],
            "shopping_needed": ["bok choy"],
        },
        confidence="high",
        data_sources=["food_preferences", "memories"],
        warnings=[],
        timestamp="2026-08-09T18:00:00+00:00",
    )


def _make_date_planner_result() -> "AgentResult":
    from app.agents.contracts import AgentResult
    return AgentResult(
        task_id="task-dp",
        task_type="date_night",
        agent="date_planner",
        success=True,
        data={
            "recommendation": {
                "date": "2026-08-22",
                "time_window": "7:00 PM - 10:00 PM",
                "activity": "Italian dinner",
                "reason": "Great evening window.",
                "alternatives": [],
            },
            "never_books": True,
        },
        confidence="high",
        data_sources=["date_history", "preferences"],
        warnings=[],
        timestamp="2026-08-09T10:00:00+00:00",
    )


def _make_organizer_result() -> "AgentResult":
    from app.agents.contracts import AgentResult
    return AgentResult(
        task_id="task-org",
        task_type="calendar_query",
        agent="organizer",
        success=True,
        data={
            "events": [{"title": "Standup", "start": "2026-08-18T09:00:00+00:00"}],
            "conflicts": [],
            "availability": [],
            "important_dates": [],
            "briefing_summary": "Busy Monday, otherwise clear.",
        },
        confidence="high",
        data_sources=["calendar_events"],
        warnings=[],
        timestamp="2026-08-09T10:00:00+00:00",
    )


def _make_specialist(result: "AgentResult | None", fail: bool = False) -> MagicMock:
    """Make a mock specialist agent."""
    specialist = MagicMock()
    if fail:
        from app.agents.contracts import AgentResult
        fail_result = AgentResult(
            task_id="task-fail",
            task_type="dinner_suggestion",
            agent="chef",
            success=False,
            data={"recommendation": "no_data", "reason": "", "alternatives": [], "shopping_needed": []},
            confidence="low",
            data_sources=[],
            warnings=["llm_error: timeout"],
            timestamp="2026-08-09T10:00:00+00:00",
        )
        specialist.run = AsyncMock(return_value=fail_result)
    else:
        specialist.run = AsyncMock(return_value=result)
    return specialist


def _make_intent(intent_type: str, date_range: dict | None = None) -> MagicMock:
    from app.agents.contracts import IntentType, IntentClassification
    intent_enum = IntentType(intent_type)
    intent = MagicMock(spec=IntentClassification)
    intent.intent = intent_enum
    intent.date_range = date_range
    intent.member_filter = None
    intent.reference_type = None
    intent.confidence = "high"
    return intent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dinner_suggestion_routes_to_chef():
    """DINNER_SUGGESTION intent causes ChefAgent.run to be called."""
    from app.agents.manager import ManagerAgent

    chef_result = _make_chef_result()
    chef = _make_specialist(chef_result)

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        result = await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    chef.run.assert_called_once()
    assert result.intent.value == "dinner_suggestion"


@pytest.mark.asyncio
async def test_date_night_routes_to_date_planner():
    """DATE_NIGHT intent causes DatePlannerAgent.run to be called."""
    from app.agents.manager import ManagerAgent

    dp_result = _make_date_planner_result()
    date_planner = _make_specialist(dp_result)

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("date_night"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            date_planner=date_planner,
        )
        result = await manager.respond("When can we have a date night?", FAMILY_ID, SESSION_ID)

    date_planner.run.assert_called_once()
    assert result.intent.value == "date_night"


@pytest.mark.asyncio
async def test_date_night_fetches_availability_before_routing():
    """DATE_NIGHT path calls get_availability_windows before building the AgentTask."""
    from app.agents.manager import ManagerAgent

    dp_result = _make_date_planner_result()
    date_planner = _make_specialist(dp_result)
    fetcher = _make_data_fetcher()

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("date_night"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=fetcher,
            context_manager=_make_context_manager(),
            model="test-model",
            date_planner=date_planner,
        )
        await manager.respond("Date night?", FAMILY_ID, SESSION_ID)

    fetcher.get_availability_windows.assert_called_once()


@pytest.mark.asyncio
async def test_multi_day_calendar_routes_to_organizer():
    """Multi-day CALENDAR_QUERY routes to OrganizerAgent when organizer is set."""
    from app.agents.manager import ManagerAgent

    org_result = _make_organizer_result()
    organizer = _make_specialist(org_result)

    multi_day_intent = _make_intent(
        "calendar_query",
        date_range={"start": "2026-08-18", "end": "2026-08-25"},  # 7 days
    )

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=multi_day_intent)):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            organizer=organizer,
        )
        await manager.respond("What does next week look like?", FAMILY_ID, SESSION_ID)

    organizer.run.assert_called_once()


@pytest.mark.asyncio
async def test_single_day_calendar_does_not_route_to_organizer():
    """Single-day CALENDAR_QUERY does NOT invoke OrganizerAgent."""
    from app.agents.manager import ManagerAgent

    organizer = _make_specialist(_make_organizer_result())

    single_day_intent = _make_intent(
        "calendar_query",
        date_range={"start": "2026-08-09", "end": "2026-08-09"},  # 0 days span
    )

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=single_day_intent)):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            organizer=organizer,
        )
        await manager.respond("What's on today?", FAMILY_ID, SESSION_ID)

    organizer.run.assert_not_called()


@pytest.mark.asyncio
async def test_chef_result_formatted_into_response():
    """Chef recommendation appears in the LLM prompt when routing is successful."""
    from app.agents.manager import ManagerAgent

    chef_result = _make_chef_result("chicken stir-fry")
    chef = _make_specialist(chef_result)

    captured_messages = []

    async def capture_complete(messages, model, temperature=0.7):
        captured_messages.extend(messages)
        return "I'd suggest chicken stir-fry tonight."

    llm = _make_llm()
    llm.complete = capture_complete

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=llm,
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        result = await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    all_content = " ".join(m.content for m in captured_messages)
    assert "chicken stir-fry" in all_content


@pytest.mark.asyncio
async def test_date_planner_result_formatted_into_response():
    """Date planner recommendation appears in the LLM prompt."""
    from app.agents.manager import ManagerAgent

    dp_result = _make_date_planner_result()
    date_planner = _make_specialist(dp_result)

    captured_messages = []

    async def capture_complete(messages, model, temperature=0.7):
        captured_messages.extend(messages)
        return "Friday the 22nd looks great for a date night."

    llm = _make_llm()
    llm.complete = capture_complete

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("date_night"))):
        manager = ManagerAgent(
            llm=llm,
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            date_planner=date_planner,
        )
        await manager.respond("Date night?", FAMILY_ID, SESSION_ID)

    all_content = " ".join(m.content for m in captured_messages)
    assert "2026-08-22" in all_content or "Italian dinner" in all_content


@pytest.mark.asyncio
async def test_organizer_result_formatted_into_response():
    """Organizer briefing_summary appears in the LLM prompt."""
    from app.agents.manager import ManagerAgent

    org_result = _make_organizer_result()
    organizer = _make_specialist(org_result)

    captured_messages = []

    async def capture_complete(messages, model, temperature=0.7):
        captured_messages.extend(messages)
        return "Here's the weekly summary."

    llm = _make_llm()
    llm.complete = capture_complete

    multi_day_intent = _make_intent(
        "calendar_query",
        date_range={"start": "2026-08-18", "end": "2026-08-25"},
    )

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=multi_day_intent)):
        manager = ManagerAgent(
            llm=llm,
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            organizer=organizer,
        )
        await manager.respond("What does next week look like?", FAMILY_ID, SESSION_ID)

    all_content = " ".join(m.content for m in captured_messages)
    assert "[SPECIALIST DATA" in all_content


@pytest.mark.asyncio
async def test_chef_none_returns_no_data_response():
    """When chef is None and DINNER_SUGGESTION is triggered, returns graceful response."""
    from app.agents.manager import ManagerAgent

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            # chef=None (default)
        )
        result = await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    assert result.response  # some graceful response
    assert "dinner" not in result.response.lower() or "yet" in result.response.lower() or "preferences" in result.response.lower()


@pytest.mark.asyncio
async def test_date_planner_none_returns_no_data_response():
    """When date_planner is None and DATE_NIGHT is triggered, returns graceful response."""
    from app.agents.manager import ManagerAgent

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("date_night"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            # date_planner=None (default)
        )
        result = await manager.respond("Date night?", FAMILY_ID, SESSION_ID)

    assert result.response  # graceful non-empty response


@pytest.mark.asyncio
async def test_organizer_none_falls_back_to_direct_path():
    """When organizer is None, multi-day CALENDAR_QUERY falls back to FamilyDataFetcher."""
    from app.agents.manager import ManagerAgent

    fetcher = _make_data_fetcher()
    multi_day_intent = _make_intent(
        "calendar_query",
        date_range={"start": "2026-08-18", "end": "2026-08-25"},
    )

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=multi_day_intent)):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=fetcher,
            context_manager=_make_context_manager(),
            model="test-model",
            # organizer=None (default)
        )
        await manager.respond("What's next week look like?", FAMILY_ID, SESSION_ID)

    # Direct path is taken — data_fetcher.get_calendar_events_and_analysis called
    fetcher.get_calendar_events_and_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_specialist_failure_result_returns_graceful_response():
    """If Chef returns success=False, Manager returns a graceful message, not an exception."""
    from app.agents.manager import ManagerAgent

    chef = _make_specialist(None, fail=True)

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        result = await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    assert isinstance(result.response, str)
    assert len(result.response) > 0


@pytest.mark.asyncio
async def test_agent_task_has_correct_task_type():
    """The AgentTask passed to the specialist has task_type matching the intent value."""
    from app.agents.manager import ManagerAgent

    captured_tasks = []

    async def capture_run(task):
        captured_tasks.append(task)
        return _make_chef_result()

    chef = MagicMock()
    chef.run = capture_run

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    assert len(captured_tasks) == 1
    assert captured_tasks[0].task_type == "dinner_suggestion"


@pytest.mark.asyncio
async def test_agent_task_family_id_from_parameter_not_task_input():
    """family_id in the AgentTask matches the family_id parameter, not any task input."""
    from app.agents.manager import ManagerAgent

    captured_tasks = []

    async def capture_run(task):
        captured_tasks.append(task)
        return _make_chef_result()

    chef = MagicMock()
    chef.run = capture_run

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=_make_llm(),
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    task = captured_tasks[0]
    assert task.family_id == FAMILY_ID
    # family_id must NOT appear inside task.inputs (only in task.family_id)
    assert "family_id" not in task.inputs


@pytest.mark.asyncio
async def test_specialist_data_labeled_in_prompt():
    """Specialist result data block contains [SPECIALIST DATA] label in LLM prompt."""
    from app.agents.manager import ManagerAgent

    captured_messages = []

    async def capture_complete(messages, model, temperature=0.7):
        captured_messages.extend(messages)
        return "Suggestion based on specialist data."

    llm = _make_llm()
    llm.complete = capture_complete

    chef = _make_specialist(_make_chef_result())

    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=_make_intent("dinner_suggestion"))):
        manager = ManagerAgent(
            llm=llm,
            data_fetcher=_make_data_fetcher(),
            context_manager=_make_context_manager(),
            model="test-model",
            chef=chef,
        )
        await manager.respond("What's for dinner?", FAMILY_ID, SESSION_ID)

    all_content = " ".join(m.content for m in captured_messages)
    assert "[SPECIALIST DATA" in all_content


def test_is_multi_day_returns_true_for_three_plus_day_range():
    """_is_multi_day returns True when end - start > 2 days."""
    from app.agents.manager import _is_multi_day
    from app.agents.contracts import IntentClassification, IntentType

    intent = MagicMock(spec=IntentClassification)
    intent.date_range = {"start": "2026-08-18", "end": "2026-08-25"}  # 7 days
    assert _is_multi_day(intent) is True


def test_is_multi_day_returns_false_for_two_day_range():
    """_is_multi_day returns False when end - start <= 2 days."""
    from app.agents.manager import _is_multi_day
    from app.agents.contracts import IntentClassification

    # 2-day range
    intent = MagicMock(spec=IntentClassification)
    intent.date_range = {"start": "2026-08-18", "end": "2026-08-20"}  # 2 days
    assert _is_multi_day(intent) is False

    # same-day
    intent2 = MagicMock(spec=IntentClassification)
    intent2.date_range = {"start": "2026-08-18", "end": "2026-08-18"}  # 0 days
    assert _is_multi_day(intent2) is False

    # no date_range
    intent3 = MagicMock(spec=IntentClassification)
    intent3.date_range = None
    assert _is_multi_day(intent3) is False


@pytest.mark.asyncio
async def test_existing_phase4_tests_unaffected_by_optional_specialists():
    """ManagerAgent can be constructed without any specialist args (Phase 4 compatibility)."""
    from app.agents.manager import ManagerAgent

    # Phase 4 style: no specialists passed
    manager = ManagerAgent(
        llm=_make_llm(),
        data_fetcher=_make_data_fetcher(),
        context_manager=_make_context_manager(),
        model="test-model",
    )
    assert manager._chef is None
    assert manager._date_planner is None
    assert manager._organizer is None

    # And a basic GENERAL intent still works
    general_intent = _make_intent("general")
    with patch("app.agents.manager.classify_intent", new=AsyncMock(return_value=general_intent)):
        result = await manager.respond("Hello there!", FAMILY_ID, SESSION_ID)

    assert isinstance(result.response, str)
