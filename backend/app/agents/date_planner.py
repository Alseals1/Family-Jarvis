"""
Date Planner Agent — date-night recommendation specialist.

Receives AgentTask from Manager. Returns AgentResult with structured
date-night recommendation.

Absolute rules:
- Never books reservations
- Never makes purchases
- Returns recommendations only — user books themselves
- "never_books": true is always present in result data
- Considers date history to avoid activity/restaurant repetition
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.contracts import AgentTask, AgentResult
from app.agents.data_fetcher import FamilyDataFetcher
from app.providers.llm.base import LLMProvider, Message

_WALL_UTC = timezone.utc


DATE_PLANNER_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["recommendation", "never_books"],
    "properties": {
        "recommendation": {
            "type": "object",
            "required": ["date", "activity", "reason"],
            "properties": {
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "time_window": {"type": "string"},   # e.g. "7:00 PM - 10:00 PM"
                "activity": {"type": "string"},
                "reason": {"type": "string"},
                "alternatives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "activity": {"type": "string"},
                        }
                    },
                    "maxItems": 2,
                },
            },
        },
        "never_books": {"type": "boolean", "enum": [True]},
    },
}


class DatePlannerAgent:
    """
    Date-night recommendation specialist.

    The Manager invokes this for DATE_NIGHT intents.

    Manager pre-fetches availability windows and passes them in task.inputs:
        {
            "availability_windows": list[dict],    # from FamilyDataFetcher.get_availability_windows
            "look_ahead_days": int,               # e.g. 30
        }

    DatePlannerAgent fetches independently:
        - date_history (last 10 dates)
        - family_preferences (category="activities")
        - family_preferences (category="dining")

    Returns AgentResult with data:
        {
            "recommendation": {
                "date": "YYYY-MM-DD",
                "time_window": "7:00 PM - 10:00 PM",
                "activity": str,
                "reason": str,
                "alternatives": list[dict],
            },
            "never_books": True,
        }

    If no availability windows exist, returns success=True with
    data["recommendation"]["date"] = None and a clear reason string.
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
        Execute date-night recommendation.

        Steps:
        1. Extract availability_windows from task.inputs
        2. If no windows: return no-availability result immediately (no LLM call)
        3. Fetch date_history, dining preferences, activity preferences
        4. Build system prompt with constraints
        5. Call LLM with complete_structured() using DATE_PLANNER_OUTPUT_SCHEMA
        6. Return AgentResult

        Never raises — returns success=False with warnings on error.
        """
        timestamp = datetime.now(_WALL_UTC).isoformat()
        family_id = task.family_id

        availability_windows = task.inputs.get("availability_windows", [])

        # Step 2: no windows — return immediately without LLM call
        if not availability_windows:
            return self._no_availability_result(task)

        # Step 3: Fetch supporting data
        try:
            date_history = await self._data.get_date_history(family_id)
            dining_preferences = await self._data.get_family_preferences(family_id, "dining")
            activity_preferences = await self._data.get_family_preferences(family_id, "activities")
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                agent="date_planner",
                success=False,
                data={
                    "recommendation": {
                        "date": None,
                        "activity": "",
                        "reason": "Data fetch error.",
                        "alternatives": [],
                    },
                    "never_books": True,
                },
                confidence="low",
                data_sources=[],
                warnings=[f"data_fetch_error: {exc}"],
                timestamp=timestamp,
            )

        # Step 4: Build system prompt
        system_prompt = self._build_system_prompt(
            availability_windows=availability_windows,
            date_history=date_history,
            dining_preferences=dining_preferences,
            activity_preferences=activity_preferences,
        )

        # Step 5: Call LLM with structured output
        try:
            structured = await self._llm.complete_structured(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(
                        role="user",
                        content=(
                            "Recommend the best date night from the available windows. "
                            "Output ONLY valid JSON matching the required schema — "
                            "never_books must always be true."
                        ),
                    ),
                ],
                schema=DATE_PLANNER_OUTPUT_SCHEMA,
                model=self._model,
            )
        except Exception as exc:
            return AgentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                agent="date_planner",
                success=False,
                data={
                    "recommendation": {
                        "date": None,
                        "activity": "",
                        "reason": "Recommendation could not be generated.",
                        "alternatives": [],
                    },
                    "never_books": True,
                },
                confidence="low",
                data_sources=["date_history", "preferences"],
                warnings=[f"llm_error: {exc}"],
                timestamp=timestamp,
            )

        # Ensure never_books is structurally always True
        recommendation = structured.get("recommendation", {})
        alternatives = recommendation.get("alternatives", [])
        # Enforce max 2 alternatives
        if len(alternatives) > 2:
            alternatives = alternatives[:2]

        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="date_planner",
            success=True,
            data={
                "recommendation": {
                    "date": recommendation.get("date"),
                    "time_window": recommendation.get("time_window", ""),
                    "activity": recommendation.get("activity", ""),
                    "reason": recommendation.get("reason", ""),
                    "alternatives": alternatives,
                },
                "never_books": True,  # structural guarantee — always True
            },
            confidence="high",
            data_sources=["date_history", "preferences"],
            warnings=[],
            timestamp=timestamp,
        )

    def _no_availability_result(self, task: AgentTask) -> AgentResult:
        """Return structured result when no shared free time was found."""
        return AgentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            agent="date_planner",
            success=True,
            data={
                "recommendation": {
                    "date": None,
                    "time_window": "",
                    "activity": "",
                    "reason": "No shared availability windows were found in the requested period.",
                    "alternatives": [],
                },
                "never_books": True,  # structural guarantee — always True
            },
            confidence="low",
            data_sources=[],
            warnings=["no_availability_windows"],
            timestamp=datetime.now(_WALL_UTC).isoformat(),
        )

    def _build_system_prompt(
        self,
        availability_windows: list[dict],
        date_history: list[dict],
        dining_preferences: dict,
        activity_preferences: dict,
    ) -> str:
        """
        Build the Date Planner system prompt.

        Includes:
        - Available windows with dates and times
        - Recent date history (to avoid repeats)
        - Dining and activity preferences
        - Hard rule: never_books must be True in output JSON
        """
        # Format availability windows
        if availability_windows:
            windows_lines = []
            for w in availability_windows:
                date_str = w.get("date", "")
                start = w.get("start_time", "")[:16] if w.get("start_time") else ""
                end = w.get("end_time", "")[:16] if w.get("end_time") else ""
                duration = w.get("duration_minutes", 0)
                windows_lines.append(
                    f"  - {date_str}: {start} to {end} ({duration} minutes free)"
                )
            windows_block = "\n".join(windows_lines)
        else:
            windows_block = "  None available."

        # Format date history to avoid repetition
        if date_history:
            history_lines = []
            for d in date_history:
                activity = d.get("activity", "")
                restaurant = d.get("restaurant", "")
                date_str = d.get("date", "")
                entry = f"  - {date_str}: {activity}"
                if restaurant:
                    entry += f" at {restaurant}"
                history_lines.append(entry)
            history_block = "\n".join(history_lines)
        else:
            history_block = "  No date history recorded yet."

        # Dining preferences
        budget = dining_preferences.get("budget", "not specified")
        cuisine = dining_preferences.get("cuisine", "no preference")

        # Activity preferences
        activity_pref = activity_preferences.get("type", "not specified")

        return (
            "You are a date-night planning assistant for a couple.\n\n"
            "CRITICAL RULE: never_books must ALWAYS be true in your JSON output. "
            "You are only providing recommendations — the couple books everything themselves.\n\n"
            "AVAILABLE WINDOWS (choose the best one):\n"
            f"{windows_block}\n\n"
            "RECENT DATE HISTORY (avoid repeating these activities/restaurants):\n"
            f"{history_block}\n\n"
            "PREFERENCES:\n"
            f"- Budget: {budget}\n"
            f"- Preferred cuisine: {cuisine}\n"
            f"- Activity preference: {activity_pref}\n\n"
            "Output ONLY valid JSON matching the required schema. "
            "No prose, no markdown, no explanations outside the JSON. "
            "never_books must be true — never include booking language in your recommendation."
        )
