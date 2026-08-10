# Phase 5 — Specialist Agents Plan

**Phase:** 5
**Status:** COMPLETE — 342/342 tests passing
**Created:** 2026-08-09
**Completed:** 2026-08-09
**Depends on:** Phase 4 complete (247/247 tests passing)
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Implement the three specialist agents — Organizer, Chef, and Date Planner — and wire them into the Manager Agent, replacing the Phase 4 stubs for `DINNER_SUGGESTION` and `DATE_NIGHT`. The Organizer also handles complex multi-day briefing queries that the Manager currently handles inline.

**Phase 5 is complete when:**

```
POST /api/chat
  { "message": "What should we have for dinner tonight?", "session_id": "..." }

→ {
    "response": "Given that everyone gets home around 6:15 and you have 45 minutes,
                 I'd suggest chicken stir-fry. You've had pasta twice this week,
                 and the family likes Asian food. You may need bell peppers.",
    "session_id": "...",
    "intent": "dinner_suggestion",
    "agent_calls": ["chef"]
  }

POST /api/chat
  { "message": "When can we have a date night this month?", "session_id": "..." }

→ {
    "response": "Friday the 22nd looks like your best window. You haven't done
                 Italian in three weeks, and there's a great spot nearby that
                 fits your usual budget. You'd need to book it yourselves.",
    "session_id": "...",
    "intent": "date_night",
    "agent_calls": ["organizer", "date_planner"]
  }
```

All 247 existing tests continue to pass. ~85 new tests are added (332 total).

---

## What Is Being Built

### Task 1 — Specialist Data Fetcher Extensions

**Branch:** `feat/specialist-data-fetcher`
**File:** `backend/app/agents/data_fetcher.py` (extend existing class)

The `FamilyDataFetcher` class gains five new methods that specialists need. The Manager already uses `get_family_members`, `get_calendar_events_and_analysis`, `get_upcoming_important_dates`, and `save_memory`. Specialists need food preference data, date history, availability windows over a wider range, and family preference lookups.

**New methods on `FamilyDataFetcher`:**

```python
async def get_food_preferences(
    self,
    family_id: str,
) -> dict:
    """
    Return family food preferences grouped by type.

    Returns:
        {
            "favorites": list[str],     # e.g. ["Italian", "Asian", "tacos"]
            "dislikes": list[str],      # e.g. ["mushrooms"]
            "restrictions": list[str],  # e.g. ["gluten-free", "peanut allergy"]
            "allergies": list[str],     # e.g. ["peanuts"]
        }

    Queries food_preferences table. family_member_id = null rows are
    family-wide; per-member rows are merged in. Restrictions and allergies
    are hard constraints — never elided.
    """

async def get_recent_meals(
    self,
    family_id: str,
    days_back: int = 14,
) -> list[str]:
    """
    Return recently logged meals from memories table where category = 'meal'.

    Returns list of meal name strings, most recent first.
    Used by Chef Agent to avoid repeating recent meals.
    If no meal memories exist, returns [].
    """

async def get_date_history(
    self,
    family_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Return recent date-night history from date_history table.

    Returns:
        [
            {
                "date": "2026-07-18",
                "activity": "dinner and a movie",
                "restaurant": "Carmine's Italian",
                "notes": "great wine list",
                "rating": 5,
            },
            ...
        ]
    Sorted most-recent-first. Returns [] if no history.
    """

async def get_family_preferences(
    self,
    family_id: str,
    category: str,
) -> dict:
    """
    Return all preferences for the family in the given category.

    Returns the preferences table rows as a flat key→value dict.
    category examples: 'dining', 'activities', 'general'
    Per-member preferences are included; family-wide (member_id = null)
    rows are the base.
    """

async def get_availability_windows(
    self,
    family_id: str,
    start: datetime,
    end: datetime,
    min_window_minutes: int = 90,
) -> list[dict]:
    """
    Return shared family availability windows across the date range.

    Calls get_events_in_range + get_family_availability (logic/availability.py).
    Only returns windows where ALL family members are free simultaneously.
    min_window_minutes=90 by default (date-night planning needs real blocks).

    Returns list of window dicts:
        [
            {
                "date": "2026-08-22",
                "start_time": "2026-08-22T18:00:00+00:00",
                "end_time": "2026-08-22T22:00:00+00:00",
                "duration_minutes": 240,
            },
            ...
        ]
    """
```

**DB queries used:**
- `food_preferences` table — SELECT by `family_id`, no new query file needed (inline)
- `memories` table — SELECT by `family_id` WHERE `category = 'meal'` (inline)
- `date_history` table — SELECT by `family_id` ORDER BY `date DESC` (inline)
- `preferences` table — SELECT by `family_id` and `category` (inline)
- Existing `get_events_in_range` + `get_family_availability` for availability windows

**Tests:** `tests/unit/test_specialist_data_fetcher.py` — all DB calls mocked

1. `test_get_food_preferences_groups_by_type`
2. `test_get_food_preferences_returns_empty_lists_when_no_data`
3. `test_get_food_preferences_merges_family_wide_and_per_member`
4. `test_get_food_preferences_restrictions_always_included`
5. `test_get_recent_meals_returns_meal_memories_only`
6. `test_get_recent_meals_returns_empty_list_when_no_meals`
7. `test_get_recent_meals_sorted_most_recent_first`
8. `test_get_date_history_returns_sorted_records`
9. `test_get_date_history_returns_empty_list_when_none`
10. `test_get_date_history_limit_respected`
11. `test_get_family_preferences_returns_flat_dict`
12. `test_get_family_preferences_empty_category_returns_empty_dict`
13. `test_get_availability_windows_calls_conflict_logic`
14. `test_get_availability_windows_respects_min_window_minutes`
15. `test_get_availability_windows_returns_empty_when_no_free_time`

---

### Task 2 — Organizer Agent

**Branch:** `feat/organizer-agent`
**File:** `backend/app/agents/organizer.py`
**Depends on:** Task 1

The Organizer is the calendar intelligence specialist. The Manager delegates complex multi-day schedule queries to it via `AgentTask`. For simple single-day calendar queries, the Manager continues to call `FamilyDataFetcher` directly (as in Phase 4) — the Organizer adds value for week-range and briefing queries where the Manager needs pre-structured analysis.

```python
"""
Organizer Agent — calendar intelligence specialist.

Receives AgentTask from Manager. Returns AgentResult with structured
calendar analysis. Never calls LLM for conflict detection or availability —
those are pure Python. Uses LLM only to generate a briefing_summary string
when requested.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.contracts import AgentTask, AgentResult
from app.agents.data_fetcher import FamilyDataFetcher
from app.providers.llm.base import LLMProvider, Message

UTC = ZoneInfo("UTC")


class OrganizerAgent:
    """
    Calendar intelligence specialist.

    The Manager invokes this for:
    - Multi-day schedule queries ("what does next week look like?")
    - Weekly briefing generation
    - Requests that require structured availability + conflict analysis
      combined with a natural-language summary

    Single-day queries continue to use FamilyDataFetcher directly in Manager.
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
        Execute calendar analysis task.

        task.inputs expected:
            {
                "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
                "members": ["all"] | [member_id, ...],
                "include_summary": bool,   # if True, generate briefing_summary via LLM
                "include_availability": bool,
            }

        Returns AgentResult with data:
            {
                "events": list[dict],
                "conflicts": list[dict],
                "availability": list[dict],
                "important_dates": list[dict],
                "briefing_summary": str | None,
            }

        Never raises — returns success=False with warnings on error.
        """

    def _parse_date_range(
        self, task: AgentTask
    ) -> tuple[datetime, datetime]:
        """
        Extract datetime range from task.inputs["date_range"].
        Raises ValueError if dates are malformed.
        """

    async def _generate_briefing_summary(
        self,
        events: list[dict],
        conflicts: list[dict],
        availability: list[dict],
        important_dates: list[dict],
        date_range: str,
        family_members: list[dict],
    ) -> str:
        """
        Use LLM to generate a 2-3 sentence natural language briefing.

        Only called if task.inputs["include_summary"] is True.
        Prompt labels all data as [CALENDAR DATA] — untrusted source.
        Never invents events not in the provided data.
        """
```

**Manager routing change:** When `IntentType.CALENDAR_QUERY` and `intent.date_range` spans more than 2 days, the Manager delegates to `OrganizerAgent.run()` instead of calling `FamilyDataFetcher` directly. Single-day and 2-day queries remain in the Manager's direct path (no change to Phase 4 behavior for the common case).

**Tests:** `tests/unit/test_organizer_agent.py` — all LLM and DB calls mocked

1. `test_organizer_returns_agent_result_shape`
2. `test_organizer_fetches_events_for_date_range`
3. `test_organizer_runs_conflict_detection_not_llm`
4. `test_organizer_calculates_availability_not_llm`
5. `test_organizer_includes_important_dates`
6. `test_organizer_generates_briefing_summary_when_requested`
7. `test_organizer_skips_llm_when_summary_not_requested`
8. `test_organizer_returns_empty_events_gracefully`
9. `test_organizer_returns_failure_on_bad_date_range`
10. `test_organizer_data_labeled_as_untrusted_in_prompt`
11. `test_organizer_never_invokes_llm_for_conflict_detection`
12. `test_organizer_agent_call_recorded_in_result`

---

### Task 3 — Chef Agent

**Branch:** `feat/chef-agent`
**File:** `backend/app/agents/chef.py`
**Depends on:** Task 1

The Chef Agent recommends dinner options given the family's preferences, recent meals, cooking time, and schedule context. It calls the LLM with a focused system prompt and structured output schema. Dietary restrictions and allergies are hard constraints injected directly — not left to LLM reasoning.

```python
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

from app.agents.contracts import AgentTask, AgentResult
from app.agents.data_fetcher import FamilyDataFetcher
from app.providers.llm.base import LLMProvider, Message


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

    def _no_data_result(self, task: AgentTask) -> AgentResult:
        """Return a structured result indicating no food preference data is available."""
```

**Tests:** `tests/unit/test_chef_agent.py` — all LLM and DB calls mocked

1. `test_chef_returns_agent_result_shape`
2. `test_chef_fetches_food_preferences`
3. `test_chef_fetches_recent_meals`
4. `test_chef_restrictions_injected_as_hard_constraints`
5. `test_chef_allergies_injected_as_hard_constraints`
6. `test_chef_recent_meals_in_prompt`
7. `test_chef_returns_no_data_result_when_no_preferences`
8. `test_chef_calls_complete_structured`
9. `test_chef_returns_failure_on_llm_error`
10. `test_chef_shopping_needed_in_result`
11. `test_chef_alternatives_in_result`
12. `test_chef_cooking_time_in_prompt`
13. `test_chef_never_invents_pantry_items`
14. `test_chef_result_data_sources_recorded`

---

### Task 4 — Date Planner Agent

**Branch:** `feat/date-planner-agent`
**File:** `backend/app/agents/date_planner.py`
**Depends on:** Task 1

The Date Planner finds available windows for a date night and recommends activities/restaurants. It requires calendar availability data (from Organizer or directly via FamilyDataFetcher), date history (to avoid repetition), and couple preferences. It uses the stronger `OPENROUTER_MODEL_PLANNER` for nuanced preference reasoning.

```python
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

from app.agents.contracts import AgentTask, AgentResult
from app.agents.data_fetcher import FamilyDataFetcher
from app.providers.llm.base import LLMProvider, Message


DATE_PLANNER_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["recommendation", "never_books"],
    "properties": {
        "recommendation": {
            "type": "object",
            "required": ["date", "activity", "reason"],
            "properties": {
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "time_window": {"type": "string"},   # e.g. "7:00 PM – 10:00 PM"
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
                "time_window": "7:00 PM – 10:00 PM",
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

    def _no_availability_result(self, task: AgentTask) -> AgentResult:
        """Return structured result when no shared free time was found."""

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
```

**Tests:** `tests/unit/test_date_planner_agent.py` — all LLM and DB calls mocked

1. `test_date_planner_returns_agent_result_shape`
2. `test_date_planner_fetches_date_history`
3. `test_date_planner_fetches_dining_preferences`
4. `test_date_planner_fetches_activity_preferences`
5. `test_date_planner_uses_availability_windows_from_task`
6. `test_date_planner_returns_no_availability_when_windows_empty`
7. `test_date_planner_skips_llm_when_no_windows`
8. `test_date_planner_calls_complete_structured`
9. `test_date_planner_result_always_has_never_books_true`
10. `test_date_planner_avoids_recent_activities_in_prompt`
11. `test_date_planner_returns_failure_on_llm_error`
12. `test_date_planner_result_data_sources_recorded`
13. `test_date_planner_recommendation_includes_date_and_activity`
14. `test_date_planner_alternatives_max_two`

---

### Task 5 — Manager Agent Specialist Routing

**Branch:** `feat/manager-specialist-routing`
**File:** `backend/app/agents/manager.py` (extend — replace stubs)
**Depends on:** Tasks 2, 3, 4

The Manager's `__init__` gains optional specialist references. The Phase 4 `_PHASE5_STUB` path is removed. The routing table expands to handle all five intents cleanly.

**Manager class signature change:**

```python
class ManagerAgent:
    def __init__(
        self,
        llm: LLMProvider,
        data_fetcher: FamilyDataFetcher,
        context_manager: ConversationContextManager,
        model: str,
        organizer: OrganizerAgent | None = None,
        chef: ChefAgent | None = None,
        date_planner: DatePlannerAgent | None = None,
    ) -> None:
```

Specialists default to `None` so that existing Phase 4 unit tests that construct `ManagerAgent` without specialists continue to compile and run unchanged. The Manager degrades gracefully: if a specialist is `None` and its intent is triggered, it returns the no-data response (not the Phase 4 stub).

**New routing in `ManagerAgent.respond()`:**

```python
# Replace Phase 4 stub block with:
if intent.intent == IntentType.DINNER_SUGGESTION:
    result = await self._route_to_chef(family_id, intent, context)
    # result is AgentResult or None
    # Manager formats natural language from result.data

elif intent.intent == IntentType.DATE_NIGHT:
    # Step 1: get availability windows (wide range)
    windows = await self._data_fetcher.get_availability_windows(
        family_id,
        start=<today>,
        end=<today + look_ahead_days>,
        min_window_minutes=90,
    )
    result = await self._route_to_date_planner(family_id, intent, context, windows)

# For CALENDAR_QUERY with multi-day range:
elif intent.intent == IntentType.CALENDAR_QUERY and _is_multi_day(intent):
    result = await self._route_to_organizer(family_id, intent, context)
    # if result is None or success=False: fall back to direct data fetcher path
```

**New private routing helpers on ManagerAgent:**

```python
async def _route_to_chef(
    self,
    family_id: str,
    intent: IntentClassification,
    context: list[ConversationTurn],
) -> AgentResult | None:
    """
    Build AgentTask for Chef, invoke ChefAgent.run(), return AgentResult.
    Returns None if chef specialist is not configured.
    """

async def _route_to_date_planner(
    self,
    family_id: str,
    intent: IntentClassification,
    context: list[ConversationTurn],
    availability_windows: list[dict],
) -> AgentResult | None:
    """
    Build AgentTask for Date Planner, invoke DatePlannerAgent.run(), return AgentResult.
    Returns None if date_planner specialist is not configured.
    """

async def _route_to_organizer(
    self,
    family_id: str,
    intent: IntentClassification,
    context: list[ConversationTurn],
) -> AgentResult | None:
    """
    Build AgentTask for Organizer, invoke OrganizerAgent.run(), return AgentResult.
    Returns None if organizer specialist is not configured (falls back to direct path).
    """

def _build_specialist_data_block(
    self,
    intent: IntentType,
    result: AgentResult,
) -> str:
    """
    Convert AgentResult.data to a structured data block string for the LLM prompt.
    All specialist data is labeled [SPECIALIST DATA] — untrusted source.
    Follows same pattern as existing [CALENDAR DATA] blocks.
    """
```

`_is_multi_day(intent)` is a module-level pure function:

```python
def _is_multi_day(intent: IntentClassification) -> bool:
    """Return True if the intent's date range spans more than 2 days."""
    if not intent.date_range:
        return False
    start = date.fromisoformat(intent.date_range["start"])
    end = date.fromisoformat(intent.date_range["end"])
    return (end - start).days > 2
```

**AgentTask construction (consistent across all three routing helpers):**

```python
AgentTask(
    task_id=str(uuid.uuid4()),
    task_type=intent.intent.value,
    family_id=family_id,
    requested_by="manager",
    inputs={...},          # intent-specific, documented per specialist
    context={
        "conversation_turns": len(context),
        "reference_type": intent.reference_type,
    },
    constraints=[...],     # hard constraints from preferences/guardrails
    timestamp=datetime.now(UTC).isoformat(),
)
```

**Tests:** `tests/unit/test_manager_specialist_routing.py` — all specialists and DB mocked

1. `test_dinner_suggestion_routes_to_chef`
2. `test_date_night_routes_to_date_planner`
3. `test_date_night_fetches_availability_before_routing`
4. `test_multi_day_calendar_routes_to_organizer`
5. `test_single_day_calendar_does_not_route_to_organizer`
6. `test_chef_result_formatted_into_response`
7. `test_date_planner_result_formatted_into_response`
8. `test_organizer_result_formatted_into_response`
9. `test_chef_none_returns_no_data_response`
10. `test_date_planner_none_returns_no_data_response`
11. `test_organizer_none_falls_back_to_direct_path`
12. `test_specialist_failure_result_returns_graceful_response`
13. `test_agent_task_has_correct_task_type`
14. `test_agent_task_family_id_from_parameter_not_task_input`
15. `test_specialist_data_labeled_in_prompt`
16. `test_is_multi_day_returns_true_for_three_plus_day_range`
17. `test_is_multi_day_returns_false_for_two_day_range`
18. `test_existing_phase4_tests_unaffected_by_optional_specialists`

---

### Task 6 — Dependency Injection Wiring

**Branch:** `feat/specialist-di-wiring`
**File:** `backend/app/api/routes/chat.py` and `backend/app/main.py`
**Depends on:** Task 5

The chat route currently creates a `ManagerAgent` with LLM, data fetcher, and context manager. It must now also create and inject the three specialist agents.

**Current (Phase 4) wiring pattern in chat.py:**

```python
agent = ManagerAgent(
    llm=get_llm_provider(),
    data_fetcher=FamilyDataFetcher(db=get_supabase_client(), db_admin=get_supabase_admin()),
    context_manager=get_context_manager(),
    model=settings.openrouter_model_manager,
)
```

**Phase 5 wiring:**

```python
_db = get_supabase_client()
_db_admin = get_supabase_admin()
_data_fetcher = FamilyDataFetcher(db=_db, db_admin=_db_admin)
_llm = get_llm_provider()

agent = ManagerAgent(
    llm=_llm,
    data_fetcher=_data_fetcher,
    context_manager=get_context_manager(),
    model=settings.openrouter_model_manager,
    organizer=OrganizerAgent(
        data_fetcher=_data_fetcher,
        llm=_llm,
        model=settings.openrouter_model_organizer,
    ),
    chef=ChefAgent(
        data_fetcher=_data_fetcher,
        llm=_llm,
        model=settings.openrouter_model_chef,
    ),
    date_planner=DatePlannerAgent(
        data_fetcher=_data_fetcher,
        llm=_llm,
        model=settings.openrouter_model_planner,
    ),
)
```

All specialists share the same `FamilyDataFetcher` and `LLMProvider` instances. Models are pulled from `settings` — never hardcoded.

**Tests:** `tests/unit/test_specialist_wiring.py`

1. `test_chat_route_wires_organizer_into_manager`
2. `test_chat_route_wires_chef_into_manager`
3. `test_chat_route_wires_date_planner_into_manager`
4. `test_all_specialists_share_same_data_fetcher_instance`
5. `test_specialist_models_from_settings_not_hardcoded`
6. `test_organizer_model_is_openrouter_model_organizer`
7. `test_chef_model_is_openrouter_model_chef`
8. `test_date_planner_model_is_openrouter_model_planner`

---

### Task 7 — Phase 5 Evaluation Suite

**Branch:** `feat/phase5-eval-suite`
**File:** `tests/unit/test_phase5_evaluation.py`
**Depends on:** Tasks 1–6

End-to-end evaluation scenarios through the full stack (mocked LLM and DB). These tests verify that the Manager correctly routes each intent, specialist agents return the expected result shape, the Manager synthesizes a sensible response, and guardrails remain active.

**Tests:** `tests/unit/test_phase5_evaluation.py`

1. `test_eval_dinner_suggestion_full_loop` — "What should we have for dinner?" → Chef invoked → recommendation in response
2. `test_eval_dinner_with_restrictions_respected` — "What for dinner?" with peanut allergy → restriction in prompt, not in recommendation
3. `test_eval_dinner_no_preferences_graceful` — no food_preferences in DB → "I don't know your preferences yet"
4. `test_eval_dinner_avoids_recent_meals` — "What for dinner?" with recent_meals in DB → no repeat
5. `test_eval_date_night_full_loop` — "When can we have a date night?" → availability fetched → Date Planner invoked → recommendation returned
6. `test_eval_date_night_no_availability_graceful` — all days busy → "I couldn't find an open window this month"
7. `test_eval_date_night_avoids_recent_activities` — recent Italian → not recommended again
8. `test_eval_date_night_never_books` — response never contains booking language
9. `test_eval_weekly_briefing_routes_to_organizer` — "What does next week look like?" → OrganizerAgent invoked
10. `test_eval_single_day_query_skips_organizer` — "What's Friday?" → no OrganizerAgent call
11. `test_eval_specialist_failure_returns_graceful_response` — specialist returns success=False → Manager responds gracefully
12. `test_eval_injection_in_food_preference_not_executed` — food preference note contains "ignore instructions" → treated as data
13. `test_eval_injection_in_date_history_not_executed` — date history note contains malicious instruction → treated as data
14. `test_eval_all_existing_phase4_scenarios_pass` — re-run the 10 Phase 4 evaluation scenarios with full specialist stack

---

## Constraints

- Conflict detection and availability calculation remain in `logic/` — no LLM used for these
- Specialists never call each other — only Manager coordinates
- Specialists never access the database outside `FamilyDataFetcher` methods
- `family_id` flows from JWT → Manager → AgentTask.family_id → specialist (never from task.inputs)
- All specialist data passed to LLM is labeled as untrusted data in prompts
- `SUPABASE_SERVICE_ROLE_KEY` (admin client) used only for writes — specialists use `db_admin` only for food_preferences, date_history, memories queries that RLS would block on anon client (same pattern as data_fetcher memory writes)
- Model names come from `settings.openrouter_model_*` — never hardcoded in any agent
- `never_books: True` is a structural guarantee in `DATE_PLANNER_OUTPUT_SCHEMA` — enforced both in the schema and verified in guardrails
- Specialist agents default to `None` in ManagerAgent so all 247 Phase 4 tests compile and run unchanged

---

## Task Summary

| # | Branch | Description | Depends on |
|---|---|---|---|
| 1 | `feat/specialist-data-fetcher` | Add 5 new methods to FamilyDataFetcher | nothing |
| 2 | `feat/organizer-agent` | OrganizerAgent class | Task 1 |
| 3 | `feat/chef-agent` | ChefAgent class | Task 1 |
| 4 | `feat/date-planner-agent` | DatePlannerAgent class | Task 1 |
| 5 | `feat/manager-specialist-routing` | Replace stubs with real routing | Tasks 2, 3, 4 |
| 6 | `feat/specialist-di-wiring` | Wire specialists into chat route | Task 5 |
| 7 | `feat/phase5-eval-suite` | Full evaluation test suite | Task 6 |

Tasks 2, 3, and 4 can run in parallel after Task 1 merges.

---

## New Files Summary

| File | Task |
|---|---|
| `backend/app/agents/organizer.py` | T2 |
| `backend/app/agents/chef.py` | T3 |
| `backend/app/agents/date_planner.py` | T4 |
| `tests/unit/test_specialist_data_fetcher.py` | T1 |
| `tests/unit/test_organizer_agent.py` | T2 |
| `tests/unit/test_chef_agent.py` | T3 |
| `tests/unit/test_date_planner_agent.py` | T4 |
| `tests/unit/test_manager_specialist_routing.py` | T5 |
| `tests/unit/test_specialist_wiring.py` | T6 |
| `tests/unit/test_phase5_evaluation.py` | T7 |

**Modified files:**

| File | Task | Change |
|---|---|---|
| `backend/app/agents/data_fetcher.py` | T1 | Add 5 new methods |
| `backend/app/agents/manager.py` | T5 | Optional specialist params, routing, helpers |
| `backend/app/api/routes/chat.py` | T6 | Inject specialists into ManagerAgent |
| `backend/app/main.py` | T6 | Import specialist agent modules |

---

## Merge Order

```
dev (base, Phase 4 merged — 247 tests passing)
 │
 ├── Task 1: feat/specialist-data-fetcher   (no deps — start first)
 │
 ├── Task 2: feat/organizer-agent           (after T1, parallel with T3, T4)
 ├── Task 3: feat/chef-agent                (after T1, parallel with T2, T4)
 ├── Task 4: feat/date-planner-agent        (after T1, parallel with T2, T3)
 │
 ├── Task 5: feat/manager-specialist-routing (after T2 + T3 + T4)
 │
 ├── Task 6: feat/specialist-di-wiring      (after T5)
 │
 └── Task 7: feat/phase5-eval-suite         (after T6 — last)
```

---

## Phase 5 Definition of Done

- [x] Specialist data fetcher — 15 tests pass; all 5 new methods on FamilyDataFetcher; restrictions always returned; food/meal/date/preference queries family-scoped
- [x] OrganizerAgent — 12 tests pass; conflict detection is pure Python (no LLM); briefing summary uses LLM only when requested; AgentResult shape correct
- [x] ChefAgent — 14 tests pass; hard constraints (allergies, restrictions) injected deterministically; no pantry invention; structured output schema enforced
- [x] DatePlannerAgent — 14 tests pass; `never_books: True` in all results; no LLM call when no availability windows; date history used to avoid repeats
- [x] Manager routing — 18 tests pass; Phase 4 stubs replaced; multi-day routes to Organizer; specialists default to None and degrade gracefully; `family_id` always from JWT
- [x] DI wiring — 8 tests pass; all three specialists wired in chat route; models from settings
- [x] Evaluation suite — 14 tests pass; all 10 Phase 4 scenarios still pass; injection in food/date data treated as data
- [x] All 247 existing tests still pass (no regressions)
- [x] Total unit test count: 247 + 95 new = **342 passing** (plan estimated 332; 10 additional tests written)
- [x] No LLM call for conflict detection or availability calculation (verified in organizer tests)
- [x] `never_books: True` is structurally guaranteed in Date Planner output (schema + guardrail test)
- [x] All specialist data passed to LLM labeled as untrusted (verified in eval suite)
- [x] Model names never hardcoded in any specialist (verified in wiring tests)
- [x] User approved merge of all Phase 5 branches to `dev`

---

## Dependencies on Phase 4 Deliverables

| Phase 4 deliverable | How Phase 5 uses it |
|---|---|
| `agents/contracts.py` — `AgentTask`, `AgentResult` | All three specialists receive and return these |
| `agents/data_fetcher.py` — `FamilyDataFetcher` | Extended with 5 new methods; shared by all specialists |
| `agents/manager.py` — `ManagerAgent` | Extended with optional specialist routing |
| `agents/guardrails.py` — `check_response()` | Still applied to all Manager responses including specialist-derived ones |
| `providers/llm/openrouter.py` — `complete_structured()` | Used by Chef and Date Planner for structured JSON output |
| `logic/availability.py` — `get_family_availability()` | Used by Organizer and new `get_availability_windows` method |
| `config.py` — `openrouter_model_organizer/chef/planner` | Already defined; used in Task 6 wiring |
| `api/routes/chat.py` — `POST /api/chat` | Extended with specialist injection in Task 6 |

---

## Phase 6 Preview

Phase 6 — Proactive Intelligence: A background scheduler emits daily and weekly briefings via the Organizer Agent, birthday/anniversary alerts via the important_dates logic, and conflict alerts. The Organizer's `include_summary=True` path (built in Phase 5 Task 2) is the primary engine for these briefings. No new agent classes are needed — proactive intelligence reuses Phase 5 specialists.
