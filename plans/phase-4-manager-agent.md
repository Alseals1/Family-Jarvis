# Phase 4 — Manager Agent Plan

**Phase:** 4
**Status:** PLANNED — awaiting user approval
**Created:** 2026-08-09
**Depends on:** Phase 3 complete (182/182 tests passing)
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Build the Manager Agent — the primary reasoning layer that transforms user messages into contextually-aware, data-grounded responses. Phase 4 delivers a working `POST /api/chat` endpoint backed by the full Manager orchestration loop: intent classification → data retrieval → guardrail check → response generation.

**Phase 4 is complete when:**
```
POST /api/chat
  { "message": "What's happening Friday?", "session_id": "..." }

→ {
    "response": "Friday looks pretty clear. Marcus has nothing on the calendar...",
    "session_id": "...",
    "agent_calls": ["organizer.get_schedule"]
  }
```
And all 10 evaluation scenarios from the agent architecture doc pass (mocked LLM), with the Manager correctly refusing to invent data, blocking no-send attempts, and resolving follow-up references from conversation history.

---

## What Is Being Built

### 1. Agent Contracts
`backend/app/agents/contracts.py` — shared dataclasses for Manager ↔ Specialist communication. Both Phase 4 and Phase 5 depend on these.

```python
from enum import Enum
from dataclasses import dataclass, field

class IntentType(Enum):
    CALENDAR_QUERY     = "calendar_query"
    IMPORTANT_DATE     = "important_date"
    DINNER_SUGGESTION  = "dinner_suggestion"
    DATE_NIGHT         = "date_night"
    MEMORY_SAVE        = "memory_save"
    GENERAL            = "general"
    BLOCKED            = "blocked"       # no-send, no-purchase, etc.

@dataclass
class AgentTask:
    task_id: str
    task_type: str                    # matches IntentType values
    family_id: str
    requested_by: str                 # "manager"
    inputs: dict
    context: dict
    constraints: list[str]
    timestamp: str

@dataclass
class AgentResult:
    task_id: str
    task_type: str
    agent: str                        # "organizer" | "chef" | "date_planner" | "manager"
    success: bool
    data: dict
    confidence: str                   # "high" | "medium" | "low"
    data_sources: list[str]
    warnings: list[str]
    timestamp: str

@dataclass
class ConversationTurn:
    turn_id: int
    role: str                         # "user" | "assistant"
    content: str
    timestamp: str
    agent_calls: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)

@dataclass
class IntentClassification:
    intent: IntentType
    date_range: dict | None           # {"start": "2026-08-14", "end": "2026-08-14"} or None
    member_filter: list[str] | None   # member names/IDs or None (all)
    reference_type: str | None        # "follow_up" | "date" | "person" | None
    confidence: str                   # "high" | "medium" | "low"
```

**Tests:** `tests/unit/test_agent_contracts.py`
1. `test_intent_type_values_match_expected_strings`
2. `test_agent_task_requires_all_fields`
3. `test_agent_result_requires_all_fields`
4. `test_conversation_turn_defaults_empty_lists`
5. `test_intent_classification_date_range_nullable`

---

### 2. Conversation Context Manager
`backend/app/agents/context.py` — in-memory sliding window of conversation history, keyed by session_id. Thread-safe for a single async process.

```python
class ConversationContextManager:
    MAX_TURNS: int = 10

    def __init__(self): ...

    def get_or_create(self, session_id: str, family_id: str) -> list[ConversationTurn]:
        # Returns current turns for session (empty list if new session)

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        # Appends turn; trims to MAX_TURNS (oldest dropped first)

    def clear(self, session_id: str) -> None:
        # Removes session from memory

    def get_last_n(self, session_id: str, n: int) -> list[ConversationTurn]:
        # Returns last N turns (or all if fewer than N exist)

    def session_count(self) -> int:
        # For health/monitoring — number of active sessions
```

**Tests:** `tests/unit/test_conversation_context.py`
1. `test_new_session_returns_empty_list`
2. `test_add_turn_appends_to_session`
3. `test_sliding_window_drops_oldest_turn`
4. `test_window_never_exceeds_max_turns`
5. `test_two_sessions_isolated_from_each_other`
6. `test_clear_removes_session`
7. `test_get_last_n_respects_bounds`
8. `test_session_count_tracks_active_sessions`

---

### 3. Intent Classifier
`backend/app/agents/intent.py` — classifies a user message into a structured `IntentClassification` using the LLM with structured output. The context (last few turns) is included so follow-ups ("what about Saturday?") are resolved correctly.

```python
async def classify_intent(
    message: str,
    context: list[ConversationTurn],
    llm: LLMProvider,
    model: str,
) -> IntentClassification:
    """
    Calls LLM with structured output schema.
    Returns IntentClassification.
    Falls back to GENERAL intent on parse failure — never raises.
    
    Date references are normalized to absolute ISO dates using today's date.
    "Friday" → "2026-08-14" (next upcoming Friday)
    "this weekend" → {"start": "2026-08-15", "end": "2026-08-16"}
    "today" → "2026-08-09"
    """
```

The system prompt for intent classification:
- Short and focused (not the full JARVIS persona — saves tokens)
- Provides today's date as context
- Includes the last 3 turns of history for reference resolution
- Instructs model to return strict JSON matching the schema

**Tests:** `tests/unit/test_intent_classifier.py` — all LLM calls mocked
1. `test_calendar_question_classified_correctly` — "What's happening Friday?" → CALENDAR_QUERY
2. `test_important_date_classified_correctly` — "When is our anniversary?" → IMPORTANT_DATE
3. `test_dinner_request_classified_correctly` — "What should we make for dinner?" → DINNER_SUGGESTION
4. `test_date_night_classified_correctly` — "When can we have a date night?" → DATE_NIGHT
5. `test_memory_save_classified_correctly` — "Remember that we like sushi" → MEMORY_SAVE
6. `test_no_send_request_classified_as_blocked` — "Send my wife a text" → BLOCKED
7. `test_follow_up_uses_context` — "What about Saturday?" after a Friday question resolves to Saturday date
8. `test_parse_failure_falls_back_to_general` — malformed LLM output → GENERAL, no exception
9. `test_date_normalization_friday` — "Friday" resolves to correct absolute date
10. `test_date_normalization_today` — "today" resolves to today's date

---

### 4. Family Data Fetcher
`backend/app/agents/data_fetcher.py` — the Manager's data access layer. Wraps DB queries and calendar logic into a clean interface. Agents and the Manager call this — never raw Supabase queries directly.

```python
class FamilyDataFetcher:
    def __init__(self, db, db_admin): ...

    async def get_calendar_events_and_analysis(
        self,
        family_id: str,
        start: datetime,
        end: datetime,
    ) -> dict:
        # Calls calendar DB queries + detect_conflicts + get_family_availability
        # Returns: {events, conflicts, availability, member_names}

    async def get_upcoming_important_dates(
        self,
        family_id: str,
        days_ahead: int = 30,
    ) -> list[dict]:
        # Queries important_dates, returns sorted by days_until
        # Uses logic/dates.py next_occurrence and days_until

    async def get_family_members(
        self,
        family_id: str,
    ) -> list[dict]:
        # Returns family member list (id, name, relationship)
        # Used for name validation in guardrails

    async def save_memory(
        self,
        family_id: str,
        content: str,
        category: str,
        db_admin,
    ) -> str:
        # Inserts into memories table
        # Returns confirmation string for aloud acknowledgment
```

**Tests:** `tests/unit/test_family_data_fetcher.py` — all DB calls mocked
1. `test_get_calendar_events_calls_conflict_detection`
2. `test_get_calendar_events_calls_availability_calculation`
3. `test_get_upcoming_important_dates_sorted_by_days_until`
4. `test_get_upcoming_dates_filters_to_family_id`
5. `test_get_family_members_returns_name_list`
6. `test_save_memory_inserts_to_correct_table`
7. `test_save_memory_returns_confirmation_string`

---

### 5. Guardrail Engine
`backend/app/agents/guardrails.py` — post-generation check before any response reaches the user. Enforces the no-invention, no-send, and no-external-instruction rules.

```python
@dataclass
class GuardrailResult:
    passed: bool
    violations: list[str]         # human-readable descriptions of failures
    safe_response: str | None     # set if passed=True, None if failed

def check_response(
    response: str,
    intent: IntentClassification,
    verified_names: list[str],     # from family_members table
    data_sources: list[str],       # what was actually queried
) -> GuardrailResult:
    """
    Checks:
    1. No-send rule: response must not direct user to send messages/emails/texts
       (draft language is allowed; "I'll send" or "I sent" is not)
    2. No-invention heuristic: if intent is BLOCKED, returns safe refusal
    3. For MEMORY_SAVE intent: response must include confirmation of what was saved
    Returns GuardrailResult. Never raises.
    """
```

Note: Full entity-level invention detection (checking every name against DB) is a Phase 5 enhancement — the LLM system prompt's no-invention instruction is the primary defense in Phase 4. The guardrail engine handles rule-based checks (no-send, BLOCKED intent responses) that are 100% deterministic.

**Tests:** `tests/unit/test_guardrails.py`
1. `test_clean_response_passes`
2. `test_send_directive_fails` — "I'll send your wife a message" → violation
3. `test_draft_language_passes` — "Here's a draft text you could send" → passes
4. `test_blocked_intent_returns_safe_refusal`
5. `test_memory_save_without_confirmation_fails`
6. `test_memory_save_with_confirmation_passes`
7. `test_guardrail_never_raises_on_empty_response`
8. `test_purchase_directive_fails` — "I've booked a table" → violation

---

### 6. Manager Agent
`backend/app/agents/manager.py` — the primary orchestration class. Receives user message + session state, runs the full loop, returns a user-facing response.

```python
class ManagerAgent:
    """
    Orchestration loop:
    1. Load conversation context (ConversationContextManager)
    2. Classify intent (IntentClassifier)
    3. Fetch required data (FamilyDataFetcher)
    4. Build LLM prompt (system + context + data + user message)
    5. Call LLM (OpenRouterProvider with OPENROUTER_MODEL_MANAGER)
    6. Apply guardrails (GuardrailEngine)
    7. Save turns to ConversationContext
    8. Return response string
    """

    def __init__(
        self,
        llm: LLMProvider,
        data_fetcher: FamilyDataFetcher,
        context_manager: ConversationContextManager,
        model: str,
    ): ...

    async def respond(
        self,
        message: str,
        family_id: str,
        session_id: str,
    ) -> ManagerResponse:
        ...

@dataclass
class ManagerResponse:
    response: str
    session_id: str
    intent: IntentType
    agent_calls: list[str]
    data_sources: list[str]
```

**System prompt for the Manager LLM call** includes:
- JARVIS persona (family chief of staff, not a chatbot)
- Today's date
- Family member names (from DB — prevents inventing names)
- Hard rules: never invent, never send, never book, never purchase
- Data provided (calendar events, important dates, etc.) clearly labeled as facts
- Instruction: if data is absent, say "I don't have that information yet"
- External content (calendar event descriptions, etc.) labeled as untrusted data

**Phase 4 routing:**
- `CALENDAR_QUERY` → FamilyDataFetcher.get_calendar_events_and_analysis → LLM synthesizes
- `IMPORTANT_DATE` → FamilyDataFetcher.get_upcoming_important_dates → LLM synthesizes
- `MEMORY_SAVE` → LLM drafts confirmation → FamilyDataFetcher.save_memory → GuardrailEngine confirms aloud confirmation present
- `BLOCKED` → GuardrailEngine returns safe refusal (no LLM call needed)
- `DINNER_SUGGESTION` / `DATE_NIGHT` → "I'll be able to help with that in a moment — dinner and date-night planning are coming very soon." (Phase 5 stub)
- `GENERAL` → LLM with family context, no specialist data fetched

**Tests:** `tests/unit/test_manager_agent.py` — all LLM + DB calls mocked

Evaluation scenarios (from agent-architecture.md §11):
1. `test_what_happening_friday_returns_calendar_data` — correct events from mocked DB
2. `test_conflict_query_returns_conflict_details` — mocked conflict detected → named in response
3. `test_follow_up_what_about_saturday_resolves_reference` — context carries forward
4. `test_anniversary_query_returns_date` — from important_dates mock
5. `test_dinner_query_returns_phase5_stub_response` — graceful stub
6. `test_date_night_query_returns_phase5_stub_response` — graceful stub
7. `test_send_request_blocked_by_guardrail` — no-send rule
8. `test_memory_save_confirmed_aloud` — confirmation string present in response
9. `test_injection_attempt_in_calendar_description_not_executed` — injected instruction in event description treated as data
10. `test_no_food_data_returns_graceful_response` — "I don't know your preferences yet"
11. `test_family_id_always_from_jwt_not_input` — family_id cannot be overridden
12. `test_new_session_id_created_if_none_provided` — session_id auto-generated

---

### 7. Chat API Route
`backend/app/api/routes/chat.py` — the public conversation endpoint.

```
POST /api/chat
Authorization: Bearer <JWT>

Request:
{
  "message": "What's happening Friday?",
  "session_id": "optional-uuid"       # client-managed; new session created if absent
}

Response 200:
{
  "response": "Friday looks clear...",
  "session_id": "uuid",
  "intent": "calendar_query",
  "agent_calls": ["data_fetcher.get_calendar_events_and_analysis"]
}

Response 401: JWT missing or invalid
Response 422: message is empty or missing
Response 429: rate limit (10 messages per family per minute — simple in-memory counter)
```

Security rules:
- `family_id` comes from JWT only — never from request body
- Empty message rejected with 422
- `session_id` created server-side if not provided (UUID4)
- Session not tied to family — but `family_id` always injected from JWT regardless of session
- Response never includes raw calendar event descriptions (only processed summaries)

**Tests:** `tests/unit/test_chat_route.py` — mocked ManagerAgent
1. `test_chat_requires_jwt`
2. `test_chat_returns_response_shape`
3. `test_chat_creates_session_id_if_absent`
4. `test_chat_rejects_empty_message`
5. `test_chat_family_id_from_jwt_not_body`
6. `test_chat_rate_limit_returns_429`
7. `test_chat_rate_limit_resets_after_window`
8. `test_chat_passes_session_id_to_manager`

---

## Constraints

- LLM is called **only** for intent classification and response generation — not for conflict detection, date math, or data retrieval (those remain pure Python from Phase 3)
- All LLM calls go through `OpenRouterProvider.complete()` or `complete_structured()` — never raw HTTP from agents
- `family_id` is extracted from JWT in the route — the Manager never trusts `family_id` from request body or session
- Model names come from `settings.openrouter_model_manager` — never hardcoded in agent code
- Context is in-memory only (Phase 4) — persistent conversation history is a Phase 6 concern
- Phase 5 specialist agents (Chef, Date Planner, Organizer) get **stubs** in Phase 4 that return graceful placeholder responses
- External content (calendar event titles, descriptions) is always passed to the LLM labeled as untrusted user data
- No LLM call for `BLOCKED` intents — the guardrail engine handles these without spending tokens

---

## Tasks

| # | Branch | Description | Depends on |
|---|---|---|---|
| 1 | `feat/agent-contracts` | AgentTask, AgentResult, ConversationTurn, IntentClassification dataclasses | nothing |
| 2 | `feat/conversation-context` | ConversationContextManager | Task 1 |
| 3 | `feat/intent-classifier` | classify_intent() with LLM structured output | Tasks 1+2 |
| 4 | `feat/family-data-fetcher` | FamilyDataFetcher wrapping Phase 3 logic | Task 1 |
| 5 | `feat/guardrail-engine` | GuardrailEngine — no-send, BLOCKED, memory-confirmation rules | Task 1 |
| 6 | `feat/manager-agent` | ManagerAgent orchestration loop | Tasks 1-5 |
| 7 | `feat/chat-route` | POST /api/chat + rate limiter + main.py registration | Task 6 |

Tasks 2, 4, and 5 can start in parallel after Task 1 merges. Task 3 depends on Tasks 1+2. Task 6 depends on all of 1-5. Task 7 depends on Task 6.

---

## New Files Summary

| File | Task |
|---|---|
| `backend/app/agents/contracts.py` | T1 |
| `backend/app/agents/context.py` | T2 |
| `backend/app/agents/intent.py` | T3 |
| `backend/app/agents/data_fetcher.py` | T4 |
| `backend/app/agents/guardrails.py` | T5 |
| `backend/app/agents/manager.py` | T6 |
| `backend/app/api/routes/chat.py` | T7 |
| `tests/unit/test_agent_contracts.py` | T1 |
| `tests/unit/test_conversation_context.py` | T2 |
| `tests/unit/test_intent_classifier.py` | T3 |
| `tests/unit/test_family_data_fetcher.py` | T4 |
| `tests/unit/test_guardrails.py` | T5 |
| `tests/unit/test_manager_agent.py` | T6 |
| `tests/unit/test_chat_route.py` | T7 |

**Modified files:**
- `backend/app/main.py` — register chat router (T7)

---

## Merge Order

```
dev (base, Phase 3 merged)
 │
 ├── Task 1: feat/agent-contracts          (no deps — start first)
 │
 ├── Task 2: feat/conversation-context     (after T1, parallel with T4, T5)
 ├── Task 4: feat/family-data-fetcher      (after T1, parallel with T2, T5)
 ├── Task 5: feat/guardrail-engine         (after T1, parallel with T2, T4)
 │
 ├── Task 3: feat/intent-classifier        (after T1 + T2)
 │
 ├── Task 6: feat/manager-agent            (after T1 + T2 + T3 + T4 + T5)
 │
 └── Task 7: feat/chat-route              (after T6 — last)
```

---

## Phase 4 Definition of Done

- [ ] Agent contracts — 5 tests pass; `IntentType` enum covers all intents
- [ ] ConversationContextManager — 8 tests pass; 10-turn sliding window enforced; two sessions isolated
- [ ] Intent classifier — 10 tests pass; all evaluation intents correctly classified with mocked LLM; parse failure falls back gracefully
- [ ] FamilyDataFetcher — 7 tests pass; wraps Phase 3 conflict/availability logic; never queries token columns
- [ ] GuardrailEngine — 8 tests pass; no-send rule blocks directive language; draft language passes; BLOCKED intent returns safe refusal
- [ ] ManagerAgent — 12 tests pass; all 10 evaluation scenarios pass; injection attempt in calendar description treated as data; family_id always from JWT
- [ ] Chat route — 8 tests pass; JWT required; rate limit enforced; session_id created if absent
- [ ] All 182 existing tests still pass (no regressions)
- [ ] Total unit test count: 182 + ~58 new = 240+ passing
- [ ] `chat` router registered in `backend/app/main.py`
- [ ] No LLM call for `BLOCKED` intents (verified in guardrail tests)
- [ ] No LLM call for conflict detection or date math (verified — those stay in logic/)
- [ ] Model name comes from settings, never hardcoded
- [ ] Phase 5 stubs (DINNER_SUGGESTION, DATE_NIGHT) return graceful "coming soon" responses
- [ ] User approves merge of all Phase 4 branches to `dev`

---

## Dependencies on Phase 3 Deliverables

| Phase 3 deliverable | How Phase 4 uses it |
|---|---|
| `logic/conflicts.py` — `detect_conflicts()` | FamilyDataFetcher calls this for calendar analysis |
| `logic/availability.py` — `get_family_availability()` | FamilyDataFetcher calls this for available windows |
| `logic/dates.py` — `days_until()`, `next_occurrence()` | FamilyDataFetcher uses for upcoming important dates |
| `db/queries/calendar.py` — `get_events_in_range()` | FamilyDataFetcher wraps this |
| `providers/llm/openrouter.py` — `complete()`, `complete_structured()` | Intent classifier + Manager response generation |
| `api/middleware/auth.py` — `get_current_user()` | Chat route extracts family_id from JWT |

---

## Phase 5 Preview

Phase 5 — Specialist Agents: The Organizer Agent, Chef Agent, and Date Planner Agent are implemented as full agent classes behind the `AgentTask`/`AgentResult` contract defined in Phase 4. The Manager's Phase 5 routing replaces the DINNER_SUGGESTION and DATE_NIGHT stubs with real specialist calls. The Organizer also handles complex multi-day briefings (today + rest of week).
