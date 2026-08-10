"""
Tests for ChefAgent — Phase 5 Task 3.

14 tests covering:
- result shape
- food preferences fetched
- recent meals fetched
- restrictions injected as hard constraints
- allergies injected as hard constraints
- recent meals in prompt
- no_data result when no preferences
- calls complete_structured
- failure on LLM error
- shopping_needed in result
- alternatives in result
- cooking_time in prompt
- never invents pantry items (prompt instruction present)
- data_sources recorded in result

All LLM and DB calls are mocked.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

UTC = timezone.utc

FAMILY_ID = "fam-test-chef"
TASK_ID = "task-chef-001"

DEFAULT_INPUTS = {
    "cooking_time_minutes": 45,
    "people_eating": 4,
    "budget": "medium",
}

FOOD_PREFS_WITH_DATA = {
    "favorites": ["Italian", "Asian"],
    "dislikes": ["mushrooms"],
    "restrictions": ["gluten-free"],
    "allergies": ["peanuts"],
}

FOOD_PREFS_EMPTY = {
    "favorites": [],
    "dislikes": [],
    "restrictions": [],
    "allergies": [],
}

LLM_CHEF_RESPONSE = {
    "recommendation": "chicken stir-fry",
    "reason": "Quick Asian dish the family loves, no peanuts, gluten-free sauce available",
    "alternatives": ["grilled salmon", "veggie tacos"],
    "shopping_needed": ["bok choy", "tamari sauce"],
}


def _make_task(inputs: dict | None = None) -> "AgentTask":
    from app.agents.contracts import AgentTask
    return AgentTask(
        task_id=TASK_ID,
        task_type="dinner_suggestion",
        family_id=FAMILY_ID,
        requested_by="manager",
        inputs=inputs or DEFAULT_INPUTS,
        context={"conversation_turns": 1, "reference_type": None},
        constraints=[],
        timestamp="2026-08-09T18:00:00+00:00",
    )


def _make_llm(structured_response: dict | None = None, raise_error: bool = False) -> MagicMock:
    llm = MagicMock()
    if raise_error:
        llm.complete_structured = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    else:
        llm.complete_structured = AsyncMock(
            return_value=structured_response if structured_response is not None else LLM_CHEF_RESPONSE
        )
    llm.complete = AsyncMock(return_value="")
    return llm


def _make_data_fetcher(
    food_prefs: dict | None = None,
    recent_meals: list | None = None,
    dining_prefs: dict | None = None,
    raise_error: bool = False,
) -> MagicMock:
    fetcher = MagicMock()
    if raise_error:
        fetcher.get_food_preferences = AsyncMock(side_effect=RuntimeError("DB error"))
    else:
        fetcher.get_food_preferences = AsyncMock(
            return_value=food_prefs if food_prefs is not None else FOOD_PREFS_WITH_DATA
        )
    fetcher.get_recent_meals = AsyncMock(
        return_value=recent_meals if recent_meals is not None else ["pasta", "tacos"]
    )
    fetcher.get_family_preferences = AsyncMock(
        return_value=dining_prefs if dining_prefs is not None else {"budget": "medium"}
    )
    return fetcher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chef_returns_agent_result_shape():
    """Result is an AgentResult with all required Chef fields."""
    from app.agents.chef import ChefAgent
    from app.agents.contracts import AgentResult

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert isinstance(result, AgentResult)
    assert result.agent == "chef"
    assert result.task_id == TASK_ID
    assert isinstance(result.data, dict)
    assert "recommendation" in result.data
    assert "reason" in result.data
    assert "alternatives" in result.data
    assert "shopping_needed" in result.data


@pytest.mark.asyncio
async def test_chef_fetches_food_preferences():
    """get_food_preferences is called with the correct family_id."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    agent = ChefAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    fetcher.get_food_preferences.assert_called_once_with(FAMILY_ID)


@pytest.mark.asyncio
async def test_chef_fetches_recent_meals():
    """get_recent_meals is called with the correct family_id."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    agent = ChefAgent(data_fetcher=fetcher, llm=_make_llm(), model="test-model")
    await agent.run(_make_task())

    fetcher.get_recent_meals.assert_called_once_with(FAMILY_ID)


@pytest.mark.asyncio
async def test_chef_restrictions_injected_as_hard_constraints():
    """Dietary restrictions appear in the system prompt under ABSOLUTE RESTRICTIONS."""
    from app.agents.chef import ChefAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_CHEF_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    food_prefs = {**FOOD_PREFS_EMPTY, "restrictions": ["gluten-free"]}
    fetcher = _make_data_fetcher(food_prefs=food_prefs)
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    assert "ABSOLUTE RESTRICTIONS" in system_content
    assert "gluten-free" in system_content


@pytest.mark.asyncio
async def test_chef_allergies_injected_as_hard_constraints():
    """Allergies appear in the system prompt under ABSOLUTE RESTRICTIONS."""
    from app.agents.chef import ChefAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_CHEF_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    food_prefs = {**FOOD_PREFS_EMPTY, "allergies": ["peanuts"], "favorites": ["Italian"]}
    fetcher = _make_data_fetcher(food_prefs=food_prefs)
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    assert "peanuts" in system_content
    # Must appear in the constraints section
    assert "ABSOLUTE RESTRICTIONS" in system_content


@pytest.mark.asyncio
async def test_chef_recent_meals_in_prompt():
    """Recent meals appear in the system prompt under RECENT MEALS."""
    from app.agents.chef import ChefAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_CHEF_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    fetcher = _make_data_fetcher(recent_meals=["pasta", "chicken tacos"])
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    assert "RECENT MEALS" in system_content
    assert "pasta" in system_content
    assert "chicken tacos" in system_content


@pytest.mark.asyncio
async def test_chef_returns_no_data_result_when_no_preferences():
    """When all food preference lists are empty, returns no_data result with warning."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher(food_prefs=FOOD_PREFS_EMPTY)
    llm = _make_llm()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert result.data["recommendation"] == "no_data"
    assert "no_food_preferences" in result.warnings
    # LLM should NOT be called when no preferences
    llm.complete_structured.assert_not_called()


@pytest.mark.asyncio
async def test_chef_calls_complete_structured():
    """complete_structured is called with CHEF_OUTPUT_SCHEMA when preferences exist."""
    from app.agents.chef import ChefAgent, CHEF_OUTPUT_SCHEMA

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    llm.complete_structured.assert_called_once()
    call_kwargs = llm.complete_structured.call_args
    # schema must be CHEF_OUTPUT_SCHEMA
    schema_arg = call_kwargs.kwargs.get("schema") or call_kwargs.args[1]
    assert schema_arg == CHEF_OUTPUT_SCHEMA


@pytest.mark.asyncio
async def test_chef_returns_failure_on_llm_error():
    """LLM error results in success=False with a warning, no exception raised."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm(raise_error=True)
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert result.success is False
    assert any("llm_error" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_chef_shopping_needed_in_result():
    """shopping_needed from the LLM response appears in result.data."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm(structured_response={
        **LLM_CHEF_RESPONSE,
        "shopping_needed": ["bok choy", "tamari sauce"],
    })
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert "bok choy" in result.data["shopping_needed"]
    assert "tamari sauce" in result.data["shopping_needed"]


@pytest.mark.asyncio
async def test_chef_alternatives_in_result():
    """alternatives from the LLM response appear in result.data."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm(structured_response={
        **LLM_CHEF_RESPONSE,
        "alternatives": ["grilled salmon", "veggie tacos"],
    })
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert "grilled salmon" in result.data["alternatives"]
    assert "veggie tacos" in result.data["alternatives"]


@pytest.mark.asyncio
async def test_chef_cooking_time_in_prompt():
    """cooking_time_minutes from task.inputs appears in the system prompt."""
    from app.agents.chef import ChefAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_CHEF_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    fetcher = _make_data_fetcher()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task({"cooking_time_minutes": 30, "people_eating": 3, "budget": "low"}))

    system_content = next(m.content for m in captured if m.role == "system")
    assert "30" in system_content


@pytest.mark.asyncio
async def test_chef_never_invents_pantry_items():
    """System prompt contains explicit instruction not to invent pantry items."""
    from app.agents.chef import ChefAgent

    captured: list = []

    async def capture_structured(messages, schema, model):
        captured.extend(messages)
        return LLM_CHEF_RESPONSE

    llm = MagicMock()
    llm.complete_structured = capture_structured

    fetcher = _make_data_fetcher()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    await agent.run(_make_task())

    system_content = next(m.content for m in captured if m.role == "system")
    # Prompt must explicitly warn against inventing pantry items
    assert "invent pantry" in system_content.lower() or "do not invent" in system_content.lower()


@pytest.mark.asyncio
async def test_chef_result_data_sources_recorded():
    """result.data_sources includes food_preferences and memories."""
    from app.agents.chef import ChefAgent

    fetcher = _make_data_fetcher()
    llm = _make_llm()
    agent = ChefAgent(data_fetcher=fetcher, llm=llm, model="test-model")
    result = await agent.run(_make_task())

    assert "food_preferences" in result.data_sources
    assert "memories" in result.data_sources
