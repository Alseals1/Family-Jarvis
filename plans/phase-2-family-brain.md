# Phase 2 — Family Brain Plan

**Phase:** 2
**Status:** PLANNED — awaiting implementation
**Created:** 2026-08-09
**Depends on:** Phase 1 complete ✅
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Build the full family data model: all remaining entities migrated, RLS enforced on every table, CRUD API routes for core family data, and a complete demo seed. The Manager Agent (Phase 4) reads from this brain — if the data model is wrong or leaky, all downstream phases break.

**Phase 2 is complete when:**
```
Family A's data is provably invisible to Family B's authenticated user.
All 12 remaining entity tables are migrated with RLS.
Demo seed loads cleanly for all entities.
Core CRUD endpoints return correct data scoped to the requesting family.
```

---

## Constraints

- No UI — backend + DB only
- All queries include `family_id` from JWT (belt) + RLS (suspenders)
- `SUPABASE_SERVICE_ROLE_KEY` only for seed/admin writes — never user requests
- Demo seed must cover edge cases agents will need: busy week, conflict, anniversary approaching
- `JARVIS_DEMO=true` in development
- Every task: own branch off `dev`, tests pass before merge

---

## New Entities (Phase 2)

These are added on top of Phase 1's `families`, `family_members`, `conversations`, and `conversation_turns`:

| Entity | Purpose |
|---|---|
| `calendars` | Calendar connections per member (Google, Apple, manual) |
| `calendar_events` | Normalized events from all providers |
| `important_dates` | Birthdays, anniversaries, trips, traditions |
| `preferences` | General family/member key-value preferences |
| `food_preferences` | Favorites, dislikes, dietary restrictions, allergies |
| `recipes` | Saved meal ideas |
| `pantry_items` | Available pantry items (future use) |
| `trips` | Planned travel |
| `relationships` | Partner, parent-child, sibling links between members |
| `date_history` | Past date nights for Date Planner context |
| `memories` | Explicitly saved facts (always confirmed to user) |
| `notifications` | Proactive alert queue |
| `agent_tasks` | Background + async agent task log |

---

## Tasks

### Task 1 — DB Migrations: All Remaining Entities
**Branch:** `feat/db-migrations-phase2`
**Branch off:** `dev`

Migrations to write (`supabase/migrations/`):
- `005_create_calendars.sql` — calendars + indexes
- `006_create_calendar_events.sql` — calendar_events + composite indexes on (family_id, start_time)
- `007_create_important_dates.sql` — important_dates + index on (family_id, date)
- `008_create_preferences.sql` — preferences + food_preferences
- `009_create_memories.sql` — memories (explicit only, always confirmed)
- `010_create_trips.sql` — trips
- `011_create_relationships.sql` — relationships + date_history
- `012_create_notifications.sql` — notifications
- `013_create_agent_tasks.sql` — agent_tasks
- `014_rls_phase2.sql` — RLS enabled + policies for every new table

RLS rules (apply to ALL tables):
- `SELECT`: `family_id IN (SELECT family_id FROM family_members WHERE user_id = auth.uid())`
- Tokens from OAuth (`access_token_enc`, `refresh_token_enc`) are **never** returned in SELECT policies — they are write-only via service role

**Tests:** Extend `test_migrations.py`
- All 14 migration files exist and are numbered sequentially
- All new tables appear in their migration files
- Every table with `family_id` has a corresponding `ROW LEVEL SECURITY` statement in `014_rls_phase2.sql`
- `access_token_enc` and `refresh_token_enc` are NOT in any SELECT policy (verified by regex)

Done when: 14 migrations present, all RLS tests pass.

---

### Task 2 — Family ID in Auth
**Branch:** `feat/auth-family-id`
**Branch off:** `dev`
**Depends on:** Task 1 merged

`/api/auth/me` currently returns `{user_id, email}`. Phase 4 agents need `family_id` on every request. Add the lookup now so all downstream tasks can use it.

**Changes:**
- `app/db/queries/family.py` — `get_family_id_for_user(user_id: str) -> str | None`
  Uses admin client to query `family_members WHERE user_id = ?` — returns `family_id`
- `app/api/middleware/auth.py` — extend `get_current_user()` to also look up and attach `family_id`
  If no `family_id` found (user hasn't completed onboarding): `family_id = None` — not an error
- `app/api/routes/auth.py` — `/api/auth/me` now returns `{user_id, email, family_id}`

**Tests:** `tests/unit/test_auth_family_id.py`
- Valid JWT + user in `family_members` → returns `family_id`
- Valid JWT + user NOT in `family_members` → `family_id: null` (not 401)
- `family_id` comes from DB lookup, never from request body

Done when: `/api/auth/me` includes `family_id`, 3 new tests pass, existing 5 auth tests still pass.

---

### Task 3 — Family Members API
**Branch:** `feat/family-members-api`
**Branch off:** `dev`
**Depends on:** Tasks 1 + 2 merged

Expose CRUD for the family's member roster. This powers onboarding (Phase 4) and gives agents their member list.

**Routes:** `app/api/routes/family_members.py` (prefix `/api/family/members`)
```
GET    /api/family/members          → list all members for authenticated family
POST   /api/family/members          → create a new member
GET    /api/family/members/{id}     → get one member
PATCH  /api/family/members/{id}     → update a member
DELETE /api/family/members/{id}     → soft-delete (set active=false)
```

**Pydantic models:** `app/models/family.py`
- `FamilyMemberCreate`, `FamilyMemberUpdate`, `FamilyMemberResponse`

**Security rules enforced in route handlers:**
- `family_id` always injected from JWT, never from request body
- DELETE only sets `active=False` — no hard deletes in MVP

**Tests:** `tests/unit/test_family_members_api.py`
- GET returns only members for authenticated family (not other families)
- POST creates member with correct `family_id` from JWT
- PATCH updates only the named fields
- DELETE sets `active=False`, member still retrievable
- Cross-family read attempt returns empty list (not 403 — RLS handles it silently)

Done when: all 5 routes tested, family isolation verified in tests.

---

### Task 4 — Important Dates API
**Branch:** `feat/important-dates-api`
**Branch off:** `dev`
**Depends on:** Tasks 1 + 2 merged (parallel with Task 3)

Important dates are the core of JARVIS's proactive intelligence — birthdays, anniversaries, trips. The Manager and Organizer agents query these constantly.

**Routes:** `app/api/routes/important_dates.py` (prefix `/api/family/dates`)
```
GET    /api/family/dates            → list all, optional ?type=birthday|anniversary|trip
POST   /api/family/dates            → create
PATCH  /api/family/dates/{id}       → update
DELETE /api/family/dates/{id}       → hard delete (user intent is explicit)
GET    /api/family/dates/upcoming   → dates within next N days (default 30)
```

**Pydantic models:** `app/models/important_dates.py`
- `ImportantDateCreate`, `ImportantDateResponse`, `UpcomingDatesResponse`

**Tests:** `tests/unit/test_important_dates_api.py`
- GET filters by `type` correctly
- `/upcoming` returns only dates within the requested window
- Yearly recurrence logic (next occurrence of a past date) calculated in Python, not LLM
- Family isolation: family A's dates invisible to family B

Done when: `/upcoming` endpoint works correctly with date math; all tests pass.

---

### Task 5 — Preferences & Food Preferences API
**Branch:** `feat/preferences-api`
**Branch off:** `dev`
**Depends on:** Tasks 1 + 2 merged (parallel with Tasks 3 + 4)

The Chef Agent and Date Planner read preferences to make recommendations.

**Routes:**
`/api/family/preferences` — key/value general preferences (member-level or family-wide)
`/api/family/food` — food preferences (favorites, dislikes, restrictions, allergies)

Both follow the same pattern as Task 3 (GET list, POST, PATCH, DELETE).

**Special rules:**
- `preference_type = 'allergy'` is a hard constraint — Chef Agent must always respect it
- A preference with `family_member_id = null` applies to the whole family

**Tests:** `tests/unit/test_preferences_api.py`
- Family-wide preferences (null member_id) returned for all members' queries
- Member-level preference does not leak to other families
- Allergy type correctly persisted and retrievable

Done when: both preference endpoints tested; allergy type distinction verified.

---

### Task 6 — Full Demo Seed
**Branch:** `feat/demo-seed-full`
**Branch off:** `dev`
**Depends on:** Task 1 merged

Expand `supabase/seed/demo-family.sql` to cover all new entities. The seed must support all Phase 4 evaluation scenarios:

**The Reeds seed must include:**
- Marcus + Priya's anniversary (14 days from a reference date)
- Eli's birthday (approaching in 10 days from reference)
- Zoe's birthday (3 months out)
- A family trip (2 weeks away)
- This week's calendar events: conflict Saturday 10am (Marcus: soccer, Priya: appointment)
- A free evening this Friday (no events after 6pm)
- Food: family likes Italian and tacos; Priya is vegetarian; Eli allergic to peanuts
- Date history: last 3 date nights (Italian, movie, hiking)
- Memories: "We like the corner table at Rosso restaurant"
- Preferences: dinner budget $50-$80, date night budget $150, cooking skill medium

Use deterministic dates relative to `2026-08-09` so tests are stable (not relative to "today").

**Tests:** `tests/unit/test_demo_seed.py`
- SQL file parses without syntax errors (load and scan for expected table names)
- All expected entities represented (important_dates, food_preferences, memories, etc.)
- Peanut allergy present for Eli
- Anniversary date is present in important_dates
- Demo family ID matches Phase 1 seed (`00000000-0000-0000-0000-000000000001`)

Done when: seed test passes; seed covers all evaluation scenario prerequisites.

---

### Task 7 — Family Isolation Integration Test
**Branch:** `feat/family-isolation-test`
**Branch off:** `dev`
**Depends on:** Tasks 1–6 merged

The most important correctness test in Phase 2: prove that one authenticated user cannot access another family's data — even with a valid JWT.

**File:** `tests/unit/test_family_isolation.py`

**Test cases (all mocked — no real Supabase call):**
1. `test_family_a_cannot_read_family_b_members` — two families, two users; user A's token returns only family A members
2. `test_family_a_cannot_read_family_b_important_dates` — same isolation for dates
3. `test_family_id_always_from_jwt_not_body` — POST /api/family/members with a spoofed `family_id` in body uses JWT family_id instead
4. `test_no_family_id_in_jwt_returns_null_not_crash` — unonboarded user gets `family_id: null`, not 500
5. `test_service_role_bypasses_rls_safely` — admin client used only in background job context, not user-facing routes

Done when: all 5 isolation tests pass.

---

## Merge Order

```
dev (base)
 ├── Task 1: feat/db-migrations-phase2       (no deps — start first)
 │
 ├── Task 2: feat/auth-family-id             (after T1)
 │
 ├── Task 3: feat/family-members-api         (after T1 + T2)  ─┐
 ├── Task 4: feat/important-dates-api        (after T1 + T2)   ├─ parallel
 ├── Task 5: feat/preferences-api            (after T1 + T2)  ─┘
 │
 ├── Task 6: feat/demo-seed-full             (after T1)
 │
 └── Task 7: feat/family-isolation-test      (after T1–T6 merged)
```

---

## Phase 2 Definition of Done

- [ ] 14 migration files present and sequentially numbered
- [ ] RLS enabled on all 13 family-scoped tables (including Phase 1)
- [ ] `auth.uid()` present in every SELECT policy (verified by test)
- [ ] OAuth token columns not exposed in SELECT policies
- [ ] `/api/auth/me` returns `family_id` (null if unonboarded, not error)
- [ ] `GET /api/family/members` returns only authenticated family's members
- [ ] `GET /api/family/dates/upcoming` returns correct upcoming dates
- [ ] `GET /api/family/food` returns preferences including allergy types
- [ ] Demo seed covers: anniversary, approaching birthday, calendar conflict, free evening, vegetarian preference, peanut allergy, date history, memories
- [ ] Family isolation test: Family A cannot read Family B data (5/5 cases)
- [ ] All backend unit tests passing (target: ~55+)
- [ ] No API keys in browser, no family_id spoofable from request body

---

## Phase 3 Preview

Phase 3 — Calendar Intelligence: GoogleCalendarProvider, event normalization, conflict detection (Python), availability calculation (Python), daily/weekly briefing data shapes. Tests with fixture data before any real calendar is connected.
