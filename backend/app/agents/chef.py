"""
Chef Agent — dinner recommendation specialist.

Receives AgentTask from Manager. Returns AgentResult with structured
dinner recommendation. Uses LLM for recommendation reasoning.

Hard constraints:
- Dietary restrictions and allergies are injected as absolute rules
- Recent meals list is injected to prevent repetition
- Never invents pantry items — only uses confirmed data
- Returns structured output — Manager formats the user-facing response
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.agents.contracts import AgentTask, AgentResult
from app.agents.data_fetcher import FamilyDataFetcher
from app.providers.llm.base import LLMProvider, Message

_WALL_UTC = timezone.utc


# Structured output schema for Chef LLM call
CHEF_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["recommendation", "reason", "alternatives", "shopping_needed"],
    "properties": {
        "recommendation": {"type": "string"},
        "reason": {"type": "string"},
        "alternatives": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "shopping_needed": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


class ChefAgent:
    """
    Dinner recommendation specialist.

    The Manager invokes this for DINNER_SUGGESTION intents.

    Inputs in task.inputs:
        {
            "cooking_time_minutes": int,     # from schedule: time before dinner must be done
            "people_eating": int,            # from family_members count
            "budget": "low" | "medium" | "high",  # from preferences
        }

    Fetches independently (not pre-fetched by Manager):
        - food_preferences (favorites, dislikes, restrictions, allergies)
        - recent_meals (last 14 days)
        - family_preferences (category="dining") for budget/style context

    Returns AgentResult with data:
        {
            "recommendation": str,
            "reason": str,
            "alternatives": list[str],
            "shopping_needed": list[str],
        }
    """

    def __init__(
        self,
        data_fetcher: FamilyDataFetcher,
        llm: LLMProvider,
        model: str,
    ) -> None:
        self._data = data_fetcher
        self._llm = llm
        self._model = model

    async def run(self, task: AgentTask) -> AgentResult:
        """
        Execute dinner recommendation.

        Steps:
        1. Fetch food_preferences, recent_meals, family_preferences
        2. Build system prompt with hard constraints
        3. Call LLM with complete_structured() using CHEF_OUTPUT_SCHEMA
        4. Return AgentResult

        Never raises — returns success=False with warnings on error.
        If no food preference data exists, returns AgentResult with
        warning "no_food_preferences" and data recommendation="no_data".
        """
        timestamp = datetime.now(_WALL_UTC).isoformat()
        family_id = task.family_id

        try:
            food_preferences = await self._data.get_food_preferences(family_id)
            recent_meals = await self._data.get_recent_meals(family_id)
            dining_preferences = await self._data.get_family_preferences(family_id, "dining")
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                agent="chef",
                success=False,
                data={
                    "recommendation": "no_data",
                    "reason": "",
                    "alternatives": [],
                    "shopping_needed": [],
                },
                confidence="low",
                data_sources=[],
                warnings=[f"data_fetch_error: {exc}"],
                timestamp=timestamp,
            )

        # Check if any meaningful preference data exists
        has_preferences = any(
            food_preferences.get(key)
            for key in ("favorites", "restrictions", "allergies", "dislikes")
        )
        if not has_preferences:
            return self._no_data_result(task)

        cooking_time_minutes = task.inputs.get("cooking_time_minutes", 60)
        people_eating = task.inputs.get("people_eating", 2)
        budget = task.inputs.get("budget") or dining_preferences.get("budget", "medium")

        system_prompt = self._build_system_prompt(
            cooking_time_minutes=cooking_time_minutes,
            people_eating=people_eating,
            food_preferences=food_preferences,
            recent_meals=recent_meals,
            budget=str(budget),
        )

        try:
            structured = await self._llm.complete_structured(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(
                        role="user",
                        content=(
                            "Recommend a dinner for tonight. "
                            "Output ONLY valid JSON matching the schema — no prose, no markdown."
                        ),
                    ),
                ],
                schema=CHEF_OUTPUT_SCHEMA,
                model=self._model,
            )
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                agent="chef",
                success=False,
                data={
                    "recommendation": "no_data",
                    "reason": "",
                    "alternatives": [],
                    "shopping_needed": [],
                },
                confidence="low",
                data_sources=["food_preferences", "memories"],
                warnings=[f"llm_error: {exc}"],
                timestamp=timestamp,
            )

        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="chef",
            success=True,
            data={
                "recommendation": structured.get("recommendation", ""),
                "reason": structured.get("reason", ""),
                "alternatives": structured.get("alternatives", []),
                "shopping_needed": structured.get("shopping_needed", []),
            },
            confidence="high",
            data_sources=["food_preferences", "memories", "preferences"],
            warnings=[],
            timestamp=timestamp,
        )

    def _build_system_prompt(
        self,
        cooking_time_minutes: int,
        people_eating: int,
        food_preferences: dict,
        recent_meals: list[str],
        budget: str,
    ) -> str:
        """
        Build the Chef system prompt.

        Hard constraint format:
            ABSOLUTE RESTRICTIONS (never suggest anything containing):
            - peanuts (allergy)
            - gluten

            RECENT MEALS (do not repeat these):
            - pasta (3 days ago)
            - chicken tacos (6 days ago)

        The prompt instructs the LLM to output only the JSON schema —
        no prose, no markdown.
        """
        allergies = food_preferences.get("allergies", [])
        restrictions = food_preferences.get("restrictions", [])
        favorites = food_preferences.get("favorites", [])
        dislikes = food_preferences.get("dislikes", [])

        # Hard constraints block
        hard_constraints_lines = []
        for allergy in allergies:
            hard_constraints_lines.append(f"- {allergy} (allergy)")
        for restriction in restrictions:
            hard_constraints_lines.append(f"- {restriction}")
        hard_constraints_block = "\n".join(hard_constraints_lines) if hard_constraints_lines else "- None"

        # Recent meals block
        recent_meals_lines = [f"- {meal}" for meal in recent_meals] if recent_meals else ["- None"]
        recent_meals_block = "\n".join(recent_meals_lines)

        # Favorites and dislikes
        favorites_str = ", ".join(favorites) if favorites else "not specified"
        dislikes_str = ", ".join(dislikes) if dislikes else "none"

        return (
            f"You are a family dinner recommendation assistant.\n\n"
            f"ABSOLUTE RESTRICTIONS (never suggest anything containing):\n"
            f"{hard_constraints_block}\n\n"
            f"RECENT MEALS (do not repeat these):\n"
            f"{recent_meals_block}\n\n"
            f"Family preferences:\n"
            f"- Cooking time available: {cooking_time_minutes} minutes\n"
            f"- People eating: {people_eating}\n"
            f"- Budget: {budget}\n"
            f"- Favorite cuisines/foods: {favorites_str}\n"
            f"- Dislikes: {dislikes_str}\n\n"
            f"Important: Do NOT invent pantry items — only list shopping_needed items "
            f"that are clearly required but may not be stocked.\n\n"
            f"Output ONLY valid JSON matching the required schema. No prose, no markdown, "
            f"no explanations outside the JSON."
        )

    def _no_data_result(self, task: AgentTask) -> AgentResult:
        """Return a structured result indicating no food preference data is available."""
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="chef",
            success=True,
            data={
                "recommendation": "no_data",
                "reason": "No food preferences are set up yet for this family.",
                "alternatives": [],
                "shopping_needed": [],
            },
            confidence="low",
            data_sources=["food_preferences"],
            warnings=["no_food_preferences"],
            timestamp=datetime.now(_WALL_UTC).isoformat(),
        )
