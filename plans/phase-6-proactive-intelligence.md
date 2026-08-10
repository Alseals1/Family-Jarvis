# Phase 6 — Proactive Intelligence Plan

**Phase:** 6
**Status:** COMPLETE — 447/447 tests passing
**Created:** 2026-08-10
**Decisions locked:** 2026-08-10
**Depends on:** Phase 5 complete (342/342 tests passing)
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Add a proactive intelligence layer to Family JARVIS. The system should notice
things without being asked — upcoming birthdays, conflicts, free evenings, dinner
suggestions — and surface them as queryable notifications. No push delivery in
this phase; notifications are data records that the frontend will poll.

**Phase 6 is complete when:**

```
GET /api/briefing?type=morning
→ {
    "type": "morning",
    "generated_at": "2026-08-10T07:00:00+00:00",
    "content": "Good morning. Today you have Emma's soccer practice at 4 PM
                and a dinner reservation at 7. Your anniversary is in 12 days —
                Friday evening is currently open.",
    "notifications": [
      { "type": "anniversary", "days_until": 12, "label": "Anniversary" },
      { "type": "conflict",    "detail": "Saturday: Emma and Alex overlap at 10 AM" }
    ]
  }

GET /api/notifications
→ {
    "pending": [
      { "id": "...", "type": "birthday", "content": "...", "trigger_date": "..." },
      ...
    ]
  }
```

All 342 existing tests continue to pass. ~95 new tests are added.

---

## Architecture Decisions (Locked)

These three decisions were confirmed by the user on 2026-08-10. They are not
open questions. Implementers must not re-open them without orchestrator approval.

### Decision 1 — Scheduler: APScheduler in-process with FastAPI lifespan

APScheduler 3.10.x runs inside the FastAPI process, started and stopped via the
FastAPI lifespan context manager. No Redis. No separate worker process. No Render
Cron Job service. The scheduler is initialized once per process in
`backend/app/jobs/scheduler.py` and wired into `backend/app/main.py`.

Rationale: zero additional infrastructure, matches the "no dedicated home server"
constraint, idempotent jobs guard against duplicate runs on restart.

### Decision 2 — Timezone: Fixed UTC schedules tuned for US Eastern; per-family deferred to Phase 9

All cron triggers are fixed UTC times selected to approximate sensible local
times for a US Eastern family:

| Job | UTC | US Eastern |
|---|---|---|
| Morning briefing | 11:00 | 07:00 |
| Important dates | 12:00 | 08:00 |
| Conflict alerts | 13:00 | 09:00 |
| Free evening check | 20:00 | 16:00 |
| Evening briefing | 22:00 | 18:00 |

Per-family timezone scheduling (running each family's jobs at their local 7 AM)
is deferred to Phase 9. Job functions accept a `timezone_str` parameter so the
per-family path requires no interface change — only scheduler registration logic
changes in Phase 9.

### Decision 3 — Briefing fallback: GET /api/briefing generates on-demand via LLM

When `GET /api/briefing` is called and no notification row exists for today
(because the scheduler has not run yet, or the process restarted), the endpoint
calls the corresponding job function on-demand, generates the briefing via the
Organizer Agent (LLM), and returns the result without storing a notification row.
This avoids empty responses during development and on first deploy. Storing the
on-demand result is intentionally skipped — the scheduler owns notification
persistence.

---

## Scheduler Decision

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| APScheduler (in-process) | Zero extra infra, works on Render free tier, no Redis, simple | Jobs die on deploy; Render free tier has 15-min sleep; OK for startup |
| External cron (Render Cron Jobs) | Reliable, survives restarts | Separate service, more config |
| FastAPI lifespan background task | Pure stdlib, no deps | No cron semantics, fires once per startup |

### Decision: APScheduler (in-process) with lifespan wiring

**Rationale:**
- No Redis, no separate worker process — matches the architecture constraint
  ("no dedicated home server or extra infrastructure")
- Render paid tier keeps the process alive; free tier is development-only
- APScheduler 3.x is pure Python, installs with pip, no system deps
- Jobs are idempotent: re-running a job that already ran today writes a duplicate
  notification check (guarded by `delivered=false` filter)
- The scheduler is started in `app/main.py` via FastAPI lifespan; it is
  initialized once per process, not per request
- If the process restarts (deploy, crash), jobs fire again at the next scheduled
  time — acceptable for notifications (no data loss, no double-send risk because
  we store/check records)
- Future: if Render background workers are enabled, jobs can be extracted with
  zero code changes (scheduler and job functions are already isolated in
  `app/jobs/`)

**APScheduler version:** 3.10.x (stable, widely used, no async dependency hell)

**Import budget:** `apscheduler` adds ~2 MB; acceptable.

---

## Notification Model

Notifications are rows in the existing `notifications` table:

```sql
notifications(
  id, family_id, type, content, trigger_date,
  delivered, delivered_at, created_at
)
```

`type` values for Phase 6:
- `morning_briefing`
- `evening_briefing`
- `birthday`
- `anniversary`
- `trip`
- `conflict`
- `free_evening`
- `dinner_suggestion`

### Write path (scheduler jobs — server-side)

Jobs use `SUPABASE_SERVICE_ROLE_KEY` (admin client) to write notification rows.
They never have a user JWT. They bypass RLS intentionally — the service role
key is the authorization.

### Read path (API — user-facing)

`GET /api/notifications` and `GET /api/briefing` read from the `notifications`
table using the **anon client** scoped to `family_id` extracted from the JWT.
RLS enforces family isolation at the DB layer.

### Deduplication

Before inserting a notification, each job queries for an existing undelivered
row of the same `(family_id, type, trigger_date)`. If one exists, the job
skips insertion. This makes all jobs idempotent.

### Delivered flag

When the frontend fetches a notification via `GET /api/notifications`, the
backend marks it `delivered=true`. The `/api/briefing` endpoint does NOT mark
delivered (briefings are re-readable). This keeps the notification inbox clean
without requiring the frontend to call a separate PATCH.

---

## Jobs Architecture

All jobs live in `backend/app/jobs/`. The scheduler is initialized in
`backend/app/jobs/scheduler.py` and started/stopped in `backend/app/main.py`
via FastAPI lifespan.

```
backend/app/jobs/
├── __init__.py          (already exists, empty — will import scheduler)
├── scheduler.py         (APScheduler setup + job registration)
├── morning_briefing.py  (daily morning job)
├── evening_briefing.py  (daily evening job)
├── important_dates.py   (birthday, anniversary, trip alert job)
├── conflict_alerts.py   (weekly conflict scan job)
├── free_evening.py      (free-evening and dinner suggestion job)
└── notifications.py     (shared write helper — insert_notification())
```

No job calls another job. Each job is independent. All jobs call shared helpers
from `app/agents/` and `app/logic/` — the same code paths as the chat route.

---

## Job Specifications

### Job 1 — Morning Briefing

**Schedule:** Daily at 11:00 UTC (07:00 US Eastern). Per-family timezone scheduling deferred to Phase 9.
**File:** `backend/app/jobs/morning_briefing.py`

```python
async def run_morning_briefing(family_id: str, timezone_str: str) -> None:
    """
    Generate a morning briefing for the family and store it as a notification.

    Steps:
    1. Build today's date range in family timezone (midnight → 11:59 PM)
    2. Invoke OrganizerAgent with include_summary=True, date_range=today
    3. Fetch upcoming important dates (days_ahead=14) — pure Python, no LLM
    4. Assemble notification content from briefing_summary + important date alerts
    5. Call insert_notification(family_id, type="morning_briefing", content=..., trigger_date=today)

    Never raises — logs errors, does not crash the scheduler.
    Idempotent: skips if a morning_briefing already exists for today.
    """
```

The LLM call is OrganizerAgent's `_generate_briefing_summary` — same path as
the chat route. No new LLM usage pattern.

### Job 2 — Evening Briefing

**Schedule:** Daily at 22:00 UTC (18:00 US Eastern). Per-family timezone scheduling deferred to Phase 9.
**File:** `backend/app/jobs/evening_briefing.py`

```python
async def run_evening_briefing(family_id: str, timezone_str: str) -> None:
    """
    Generate an evening briefing covering tonight and tomorrow.

    Steps:
    1. Build date range: today 5 PM → tomorrow 11:59 PM (family tz)
    2. Invoke OrganizerAgent with include_summary=True, include_availability=True
    3. Extract tonight's availability windows
    4. If a free window ≥ 60 minutes exists tonight:
       - Add dinner suggestion (invoke ChefAgent with cooking_time from window)
    5. Store as notification type="evening_briefing"

    Never raises. Idempotent.
    """
```

### Job 3 — Important Dates

**Schedule:** Daily at 12:00 UTC (08:00 US Eastern). Not family-timezone-sensitive; date comparison uses UTC date.
**File:** `backend/app/jobs/important_dates.py`

```python
async def run_important_date_alerts(family_id: str) -> None:
    """
    Check all important_dates rows and emit alerts when within lead_days.

    Steps:
    1. Fetch all important_dates for the family (admin client)
    2. For each date, compute next_occurrence() and days_until() — pure Python
    3. If days_until <= lead_days AND no notification exists for
       (family_id, type=date_type, trigger_date=occurrence):
       - Insert notification row
       - type = "birthday" | "anniversary" | "trip" | "other"
       - content = plain English alert (no LLM — pure string formatting)
         e.g. "Emma's birthday is in 7 days — August 17."

    Alert content is constructed deterministically — no LLM.
    Never raises. Idempotent per (family_id, type, trigger_date).
    """
```

Content format:
- Birthday: `"{name}'s birthday is in {N} days — {date}."`
- Anniversary: `"Your anniversary is in {N} days — {date}. Friday is currently your best open evening."` (availability check added only if `N <= 14`)
- Trip: `"Your trip to {destination} departs in {N} days."`
- Other: `"{label} is in {N} days — {date}."`

No LLM for these strings. They are deterministic. The free-evening hint in
anniversary alerts is a simple availability query (already built in Phase 5).

### Job 4 — Conflict Alerts

**Schedule:** Daily at 13:00 UTC (09:00 US Eastern).
**File:** `backend/app/jobs/conflict_alerts.py`

```python
async def run_conflict_alerts(family_id: str) -> None:
    """
    Scan the next 7 days for calendar conflicts and emit alerts.

    Steps:
    1. Fetch calendar_events for next 7 days (get_events_in_range)
    2. Run detect_conflicts() — pure Python, no LLM
    3. For each conflict not already notified today:
       - Insert notification with type="conflict"
       - content = "Conflict {day}: {name} has {event_a} overlapping {event_b}."

    Content is deterministic — no LLM.
    Never raises. Idempotent.
    """
```

### Job 5 — Free Evening and Dinner Suggestion

**Schedule:** Daily at 20:00 UTC (16:00 US Eastern). Per-family timezone scheduling deferred to Phase 9.
**File:** `backend/app/jobs/free_evening.py`

```python
async def run_free_evening_check(family_id: str, timezone_str: str) -> None:
    """
    Check if tonight has a shared free window and optionally suggest dinner.

    Steps:
    1. Compute tonight's window: 5 PM → 10 PM (family tz)
    2. Call get_availability_windows() — pure Python
    3. If a free window ≥ 45 minutes exists:
       - Emit notification type="free_evening"
         content = "Everyone's free tonight from {start} to {end}.
                    You have about {N} minutes for dinner."
    4. Invoke ChefAgent for a dinner suggestion using cooking_time = min(window_minutes, 60)
       - Emit notification type="dinner_suggestion"
         content = "Dinner idea for tonight: {recommendation}. {reason}"
    5. Skip both if no free window found.

    Uses ChefAgent (LLM) for dinner recommendation only.
    Availability check is pure Python.
    Never raises. Idempotent.
    """
```

---

## Scheduler Initialization

**File:** `backend/app/jobs/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

def build_scheduler(db_admin) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns a configured (not yet started) scheduler.
    Jobs are registered here with their cron expressions.
    db_admin is the service-role Supabase client — passed to all job runners.

    All times in UTC unless the job itself converts to family timezone.
    """

def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Start the scheduler. Called from FastAPI lifespan startup."""

def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Graceful shutdown. Called from FastAPI lifespan shutdown."""
```

**FastAPI lifespan wiring** (`backend/app/main.py`):

```python
from contextlib import asynccontextmanager
from app.jobs.scheduler import build_scheduler, start_scheduler, stop_scheduler
from app.db.supabase import get_supabase_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler(db_admin=get_supabase_admin())
    start_scheduler(scheduler)
    yield
    stop_scheduler(scheduler)

app = FastAPI(..., lifespan=lifespan)
```

The scheduler queries all active families at job start time and runs each job
per family. The family list is fetched fresh on each job execution (so newly
onboarded families are picked up automatically without a restart).

---

## API Endpoints

### GET /api/briefing

**File:** `backend/app/api/routes/briefing.py`

```python
@router.get("/briefing")
async def get_briefing(
    type: str = "morning",           # "morning" | "evening"
    user: dict = Depends(get_current_user),
) -> BriefingResponse:
    """
    Return the most recent undelivered briefing of the given type.
    If none exists (scheduler hasn't run yet), generate one on-demand.

    family_id from JWT only.
    Does NOT mark the notification as delivered.

    Returns:
        {
            "type": "morning",
            "generated_at": "...",
            "content": "...",
            "notifications": [
                { "type": str, "content": str, "trigger_date": str }
            ]
        }
    """
```

On-demand generation (confirmed, Decision 3): if no notification row exists for
today's briefing type, the endpoint calls the corresponding job function
synchronously, generates the briefing via the Organizer Agent (LLM), and returns
the result without persisting a notification row. The scheduler owns notification
persistence; the API route owns on-demand generation. This eliminates empty
responses on first deploy or after a process restart.

### GET /api/notifications

**File:** `backend/app/api/routes/notifications.py`

```python
@router.get("/notifications")
async def get_notifications(
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> NotificationsResponse:
    """
    Return all undelivered notifications for the family, sorted newest first.

    Marks returned notifications as delivered=true automatically.
    family_id from JWT only.

    Returns:
        {
            "pending": [
                {
                    "id": "uuid",
                    "type": "birthday",
                    "content": "...",
                    "trigger_date": "2026-08-17",
                    "created_at": "..."
                }
            ],
            "count": int
        }
    """
```

---

## Shared Notification Helper

**File:** `backend/app/jobs/notifications.py`

```python
async def insert_notification(
    db_admin,
    family_id: str,
    type: str,
    content: str,
    trigger_date: date,
) -> bool:
    """
    Insert a notification row if one doesn't already exist for
    (family_id, type, trigger_date).

    Returns True if inserted, False if skipped (already exists).
    Uses admin client — no JWT context.
    """

async def get_all_family_ids(db_admin) -> list[str]:
    """
    Return all family IDs from the families table.
    Used by the scheduler to know which families to run jobs for.
    """

async def get_pending_notifications(
    db: Client,  # anon client, RLS scoped
    family_id: str,
    limit: int = 20,
) -> list[dict]:
    """
    Return undelivered notifications sorted newest first.
    family_id is the application-level filter (RLS adds DB-level filter).
    """

async def mark_delivered(
    db_admin,
    notification_ids: list[str],
) -> None:
    """
    Set delivered=true, delivered_at=now() for the given notification IDs.
    """
```

---

## Task Breakdown

### Task 1 — Shared Notification Helpers

**Branch:** `feat/notification-helpers`
**Files:**
- `backend/app/jobs/notifications.py` — insert, query, mark-delivered helpers
- `backend/app/jobs/__init__.py` — import scheduler

**Depends on:** nothing (pure DB layer)

**DB operations:**
- INSERT into `notifications` with dedup guard
- SELECT from `notifications` (pending, by family)
- UPDATE `notifications` set delivered

**Tests:** `tests/unit/test_job_notifications.py` — DB calls mocked

1. `test_insert_notification_inserts_when_no_duplicate`
2. `test_insert_notification_skips_when_duplicate_exists`
3. `test_insert_notification_dedup_key_is_family_type_date`
4. `test_get_all_family_ids_returns_list`
5. `test_get_all_family_ids_returns_empty_when_no_families`
6. `test_get_pending_notifications_returns_undelivered_only`
7. `test_get_pending_notifications_scoped_to_family`
8. `test_get_pending_notifications_sorted_newest_first`
9. `test_get_pending_notifications_respects_limit`
10. `test_mark_delivered_sets_flag_and_timestamp`
11. `test_mark_delivered_empty_list_no_op`
12. `test_insert_notification_uses_admin_client`

---

### Task 2 — Important Dates Job

**Branch:** `feat/job-important-dates`
**File:** `backend/app/jobs/important_dates.py`
**Depends on:** Task 1

This job reuses `FamilyDataFetcher.get_upcoming_important_dates()` (already
built in Phase 4) and `logic/dates.py` functions. No LLM. No new agent code.

```python
async def run_important_date_alerts(
    family_id: str,
    db_admin,
) -> list[str]:
    """
    Scan important_dates for this family and insert alert notifications.

    Returns list of inserted notification IDs (empty if all skipped).
    Uses: get_upcoming_important_dates(), days_until(), next_occurrence()
    Content format: deterministic string templates — NO LLM.
    """
```

**Tests:** `tests/unit/test_job_important_dates.py`

1. `test_birthday_alert_inserted_when_within_lead_days`
2. `test_birthday_alert_skipped_when_outside_lead_days`
3. `test_anniversary_alert_inserted_with_days_until`
4. `test_trip_alert_inserted_for_upcoming_trip`
5. `test_alert_skipped_when_duplicate_exists`
6. `test_alert_content_contains_label_and_date`
7. `test_alert_content_contains_days_until`
8. `test_birthday_type_in_notification_row`
9. `test_anniversary_type_in_notification_row`
10. `test_trip_type_in_notification_row`
11. `test_no_llm_called_for_important_date_content`
12. `test_yearly_recurrence_uses_next_occurrence`
13. `test_non_recurring_date_not_repeated`
14. `test_returns_empty_list_when_no_upcoming_dates`

---

### Task 3 — Conflict Alerts Job

**Branch:** `feat/job-conflict-alerts`
**File:** `backend/app/jobs/conflict_alerts.py`
**Depends on:** Task 1

Reuses `get_events_in_range` (Phase 3) and `detect_conflicts()` (Phase 3).
No LLM. Content is deterministic.

```python
async def run_conflict_alerts(
    family_id: str,
    db_admin,
    db,
    days_ahead: int = 7,
) -> list[str]:
    """
    Scan next N days for calendar conflicts and insert conflict notifications.

    Returns list of inserted notification IDs.
    Uses: get_events_in_range(), detect_conflicts()
    Content: deterministic — no LLM.
    """
```

**Tests:** `tests/unit/test_job_conflict_alerts.py`

1. `test_conflict_alert_inserted_when_conflict_found`
2. `test_no_alert_when_no_conflicts`
3. `test_conflict_alert_content_contains_member_name`
4. `test_conflict_alert_content_contains_event_titles`
5. `test_conflict_alert_content_contains_conflict_time`
6. `test_conflict_alert_skipped_when_duplicate_exists`
7. `test_conflict_type_in_notification_row`
8. `test_conflict_detection_uses_logic_not_llm`
9. `test_multiple_conflicts_generate_multiple_notifications`
10. `test_cancelled_events_excluded_from_conflict_scan`

---

### Task 4 — Morning and Evening Briefing Jobs

**Branch:** `feat/job-briefings`
**Files:**
- `backend/app/jobs/morning_briefing.py`
- `backend/app/jobs/evening_briefing.py`
**Depends on:** Task 1

Both jobs invoke OrganizerAgent with `include_summary=True`. The Organizer's
LLM path (already tested in Phase 5) generates the natural-language briefing.
No new agent code.

```python
async def run_morning_briefing(
    family_id: str,
    timezone_str: str,
    db_admin,
    organizer: OrganizerAgent,
) -> str | None:
    """
    Generate morning briefing and store as notification.

    Returns notification content string, or None if skipped (already exists).
    type = "morning_briefing", trigger_date = today.
    """

async def run_evening_briefing(
    family_id: str,
    timezone_str: str,
    db_admin,
    organizer: OrganizerAgent,
    chef: ChefAgent,
) -> str | None:
    """
    Generate evening briefing. Includes dinner suggestion if free window exists.

    Returns notification content string, or None if skipped.
    type = "evening_briefing", trigger_date = today.
    """
```

Agent instances are constructed by the scheduler at job time using
`get_supabase_admin()` and `get_llm_provider()` — same factory functions as
the chat route.

**Tests:** `tests/unit/test_job_briefings.py` — all LLM and DB mocked

1. `test_morning_briefing_invokes_organizer_with_include_summary_true`
2. `test_morning_briefing_stores_notification_row`
3. `test_morning_briefing_skipped_when_already_exists`
4. `test_morning_briefing_includes_important_dates_in_context`
5. `test_morning_briefing_type_is_morning_briefing`
6. `test_morning_briefing_trigger_date_is_today`
7. `test_evening_briefing_invokes_organizer_with_today_and_tomorrow`
8. `test_evening_briefing_invokes_chef_when_free_window_exists`
9. `test_evening_briefing_skips_chef_when_no_free_window`
10. `test_evening_briefing_stores_notification_row`
11. `test_evening_briefing_skipped_when_already_exists`
12. `test_briefing_content_from_organizer_summary_not_invented`
13. `test_briefing_uses_family_timezone_for_date_range`
14. `test_briefing_organizer_failure_handled_gracefully`

---

### Task 5 — Free Evening and Dinner Suggestion Job

**Branch:** `feat/job-free-evening`
**File:** `backend/app/jobs/free_evening.py`
**Depends on:** Task 1

```python
async def run_free_evening_check(
    family_id: str,
    timezone_str: str,
    db_admin,
    db,
    chef: ChefAgent,
) -> dict:
    """
    Check tonight for a shared free window and optionally suggest dinner.

    Returns dict with keys:
        "free_evening_inserted": bool
        "dinner_suggestion_inserted": bool
        "window": dict | None  — the found window
    """
```

**Tests:** `tests/unit/test_job_free_evening.py`

1. `test_free_evening_notification_inserted_when_window_found`
2. `test_free_evening_notification_not_inserted_when_no_window`
3. `test_dinner_suggestion_inserted_when_free_window_found`
4. `test_dinner_suggestion_not_inserted_when_no_window`
5. `test_dinner_suggestion_invokes_chef_with_cooking_time`
6. `test_dinner_suggestion_cooking_time_capped_at_60_minutes`
7. `test_free_evening_content_contains_window_times`
8. `test_free_evening_content_contains_duration`
9. `test_free_evening_type_in_notification_row`
10. `test_dinner_suggestion_type_in_notification_row`
11. `test_free_evening_skipped_if_already_notified_today`
12. `test_dinner_suggestion_skipped_if_already_notified_today`
13. `test_free_evening_uses_family_timezone_for_window_search`

---

### Task 6 — Scheduler Wiring

**Branch:** `feat/scheduler-wiring`
**Files:**
- `backend/app/jobs/scheduler.py` — APScheduler setup
- `backend/app/main.py` — lifespan context manager
- `backend/requirements.txt` — add `apscheduler==3.10.4`
**Depends on:** Tasks 2–5

```python
def build_scheduler(db_admin) -> AsyncIOScheduler:
    """
    Register all 5 job types with their cron schedules.
    Jobs are run per-family: each execution fetches all family IDs first.

    Schedule (all cron, UTC — tuned for US Eastern, per-family tz deferred to Phase 9):
        Morning briefing:        11:00 UTC daily  (07:00 US Eastern)
        Important dates:         12:00 UTC daily  (08:00 US Eastern)
        Conflict alerts:         13:00 UTC daily  (09:00 US Eastern)
        Free evening check:      20:00 UTC daily  (16:00 US Eastern)
        Evening briefing:        22:00 UTC daily  (18:00 US Eastern)
    """
```

Note: All schedules are fixed UTC times tuned for a US Eastern family (Decision 2).
Family timezone handling inside each job function converts the UTC trigger time to
a local date for content generation. Per-family cron scheduling (running each
family's jobs at their local 7 AM) is explicitly deferred to Phase 9. The job
function signatures already accept `timezone_str` so Phase 9 requires only
scheduler registration changes, not interface changes.

**Tests:** `tests/unit/test_scheduler.py`

1. `test_scheduler_builds_without_error`
2. `test_scheduler_has_five_jobs_registered`
3. `test_all_job_ids_are_unique`
4. `test_morning_briefing_job_is_registered`
5. `test_evening_briefing_job_is_registered`
6. `test_important_dates_job_is_registered`
7. `test_conflict_alerts_job_is_registered`
8. `test_free_evening_job_is_registered`
9. `test_scheduler_does_not_start_automatically_on_import`
10. `test_lifespan_starts_and_stops_scheduler`

---

### Task 7 — Briefing and Notifications API Routes

**Branch:** `feat/proactive-api-routes`
**Files:**
- `backend/app/api/routes/briefing.py` — GET /api/briefing
- `backend/app/api/routes/notifications.py` — GET /api/notifications
- `backend/app/main.py` — register new routers
**Depends on:** Task 1

Both routes require valid JWT. `family_id` comes from JWT only. No `family_id`
in request body or query params.

**Briefing route** (`GET /api/briefing?type=morning`):
- Reads latest notification of `type` for today from DB
- If none found: calls the corresponding job function on-demand (sync fallback)
- Does NOT mark as delivered

**Notifications route** (`GET /api/notifications?limit=20`):
- Returns all pending (undelivered) notifications for the family
- Marks all returned notifications as delivered in the same request

**Tests:** `tests/unit/test_proactive_routes.py` — DB and job functions mocked

1. `test_briefing_route_returns_200_with_valid_jwt`
2. `test_briefing_route_rejects_missing_jwt_with_401`
3. `test_briefing_family_id_from_jwt_not_query_param`
4. `test_briefing_returns_latest_notification_for_today`
5. `test_briefing_fallback_to_on_demand_when_no_row`
6. `test_briefing_type_param_morning_returns_morning_type`
7. `test_briefing_type_param_evening_returns_evening_type`
8. `test_briefing_invalid_type_returns_422`
9. `test_notifications_route_returns_200_with_valid_jwt`
10. `test_notifications_route_rejects_missing_jwt_with_401`
11. `test_notifications_family_id_from_jwt_not_query_param`
12. `test_notifications_returns_only_undelivered`
13. `test_notifications_marks_returned_as_delivered`
14. `test_notifications_sorted_newest_first`
15. `test_notifications_limit_param_respected`
16. `test_notifications_default_limit_is_20`
17. `test_notifications_returns_empty_when_none_pending`
18. `test_notifications_cannot_read_other_family_data`

---

### Task 8 — Phase 6 Evaluation Suite

**Branch:** `feat/phase6-eval-suite`
**File:** `tests/unit/test_phase6_evaluation.py`
**Depends on:** Tasks 1–7

End-to-end scenarios through the full job-and-API stack (all external calls
mocked). Verifies the proactive layer produces correct, non-invented content and
that the API surfaces it correctly.

**Tests:** `tests/unit/test_phase6_evaluation.py`

1. `test_eval_morning_briefing_full_path` — job runs → notification stored → GET /api/briefing returns it
2. `test_eval_evening_briefing_with_dinner_suggestion` — free window exists → Chef invoked → dinner_suggestion notification stored
3. `test_eval_birthday_alert_14_days_out` — birthday in 14 days → notification with correct content
4. `test_eval_birthday_alert_outside_lead_days_not_inserted` — birthday in 30 days, lead_days=14 → no notification
5. `test_eval_anniversary_alert_content_format` — anniversary in 10 days → correct string format
6. `test_eval_trip_alert_content_format` — trip in 5 days → correct string format
7. `test_eval_conflict_alert_generated_for_known_fixture` — seeded conflict → conflict notification
8. `test_eval_no_llm_called_for_deterministic_alerts` — date/conflict alerts → zero LLM calls
9. `test_eval_notifications_marked_delivered_on_fetch` — fetch notifications → delivered=true afterward
10. `test_eval_notifications_not_duplicated` — job runs twice → only one notification row
11. `test_eval_family_isolation_briefing` — family A cannot read family B briefing
12. `test_eval_family_isolation_notifications` — family A notifications not returned for family B JWT
13. `test_eval_injection_in_calendar_event_not_executed_in_briefing` — event description "ignore instructions" → treated as data in briefing
14. `test_eval_all_phase5_scenarios_unaffected` — re-run all 14 Phase 5 evaluation scenarios

---

## Constraints

- Conflict detection and date math remain in `logic/` — no LLM for these
- Alert content for birthdays, anniversaries, trips, and conflicts is
  deterministic string formatting — no LLM
- LLM is used only for: morning briefing summary (via Organizer),
  evening briefing summary (via Organizer), dinner suggestion (via Chef)
- `family_id` is never taken from job inputs or request body — always from JWT
  (API) or DB query (scheduler)
- `SUPABASE_SERVICE_ROLE_KEY` is used only in job functions — never in
  user-facing API routes
- Notifications are data records — no push delivery in Phase 6
- Jobs are idempotent: dedup check before every insert
- APScheduler errors are logged but never crash the FastAPI process
- All existing 342 tests must continue to pass

---

## Task Summary

| # | Branch | Description | Depends on | New Tests |
|---|---|---|---|---|
| 1 | `feat/notification-helpers` | Shared notification DB helpers | none | 12 |
| 2 | `feat/job-important-dates` | Birthday/anniversary/trip alert job | T1 | 14 |
| 3 | `feat/job-conflict-alerts` | Conflict scan job | T1 | 10 |
| 4 | `feat/job-briefings` | Morning + evening briefing jobs | T1 | 14 |
| 5 | `feat/job-free-evening` | Free-evening + dinner suggestion job | T1 | 13 |
| 6 | `feat/scheduler-wiring` | APScheduler + FastAPI lifespan | T2–T5 | 10 |
| 7 | `feat/proactive-api-routes` | GET /api/briefing + GET /api/notifications | T1 | 18 |
| 8 | `feat/phase6-eval-suite` | End-to-end evaluation suite | T1–T7 | 14 |

Tasks 2, 3, 4, and 5 can run in parallel after Task 1 merges.
Tasks 6 and 7 can run in parallel after Tasks 2–5 merge.

---

## Merge Order

```
dev (base, Phase 5 merged — 342 tests passing)
 │
 ├── Task 1: feat/notification-helpers      (no deps — start first)
 │
 ├── Task 2: feat/job-important-dates       (after T1, parallel with T3, T4, T5)
 ├── Task 3: feat/job-conflict-alerts       (after T1, parallel with T2, T4, T5)
 ├── Task 4: feat/job-briefings             (after T1, parallel with T2, T3, T5)
 ├── Task 5: feat/job-free-evening          (after T1, parallel with T2, T3, T4)
 │
 ├── Task 6: feat/scheduler-wiring          (after T2 + T3 + T4 + T5)
 ├── Task 7: feat/proactive-api-routes      (after T1, parallel with T6)
 │
 └── Task 8: feat/phase6-eval-suite         (after T6 + T7 — last)
```

---

## New Files Summary

| File | Task |
|---|---|
| `backend/app/jobs/notifications.py` | T1 |
| `backend/app/jobs/important_dates.py` | T2 |
| `backend/app/jobs/conflict_alerts.py` | T3 |
| `backend/app/jobs/morning_briefing.py` | T4 |
| `backend/app/jobs/evening_briefing.py` | T4 |
| `backend/app/jobs/free_evening.py` | T5 |
| `backend/app/jobs/scheduler.py` | T6 |
| `backend/app/api/routes/briefing.py` | T7 |
| `backend/app/api/routes/notifications.py` | T7 |
| `tests/unit/test_job_notifications.py` | T1 |
| `tests/unit/test_job_important_dates.py` | T2 |
| `tests/unit/test_job_conflict_alerts.py` | T3 |
| `tests/unit/test_job_briefings.py` | T4 |
| `tests/unit/test_job_free_evening.py` | T5 |
| `tests/unit/test_scheduler.py` | T6 |
| `tests/unit/test_proactive_routes.py` | T7 |
| `tests/unit/test_phase6_evaluation.py` | T8 |

**Modified files:**

| File | Task | Change |
|---|---|---|
| `backend/app/jobs/__init__.py` | T1 | Import scheduler |
| `backend/app/main.py` | T6 | Add lifespan context manager with scheduler |
| `backend/app/config.py` | T6 | No changes needed — scheduler uses existing settings |
| `backend/requirements.txt` | T6 | Add `apscheduler==3.10.4` |

---

## Definition of Done

- [x] Notification helpers — 12 tests pass; insert deduplication proven; admin client used; family scoping enforced
- [x] Important dates job — 14 tests pass; no LLM for content; lead_days respected; yearly recurrence handled; idempotent
- [x] Conflict alerts job — 10 tests pass; detect_conflicts() reused; no LLM; idempotent
- [x] Briefing jobs — 14 tests pass; Organizer's include_summary=True path reused; family timezone applied; graceful failure
- [x] Free evening job — 13 tests pass; availability logic reused (no LLM); Chef invoked only when window found; idempotent
- [x] Scheduler — 10 tests pass; 5 jobs registered; lifespan start/stop works; does not auto-start on import
- [x] API routes — 18 tests pass; JWT required; family_id from JWT only; delivered flag set on GET /api/notifications; briefing falls back on-demand
- [x] Evaluation suite — 14 tests pass; family isolation confirmed; injection in calendar data treated as data; Phase 5 scenarios unaffected
- [x] All 342 existing tests still pass (no regressions)
- [x] Total unit test count: 447 passing (342 Phase 1-5 + 105 new Phase 6 tests)
- [x] No LLM called for date alerts, conflict alerts, or availability checks (verified in eval suite)
- [x] All job functions are idempotent (duplicate run produces same DB state)
- [x] `family_id` never taken from request body or job input — always from JWT or DB scan
- [x] `SUPABASE_SERVICE_ROLE_KEY` used only in job code, never in user API routes
- [x] All Phase 6 branches merged to `dev`

---

## Dependencies on Phase 5 Deliverables

| Phase 5 deliverable | How Phase 6 uses it |
|---|---|
| `agents/organizer.py` — `OrganizerAgent.run()` with `include_summary=True` | Morning and evening briefing jobs |
| `agents/chef.py` — `ChefAgent.run()` | Evening briefing and free-evening dinner suggestion |
| `agents/data_fetcher.py` — `get_upcoming_important_dates()` | Morning briefing context; important dates job |
| `agents/data_fetcher.py` — `get_availability_windows()` | Free-evening check; anniversary alert hint |
| `logic/conflicts.py` — `detect_conflicts()` | Conflict alerts job |
| `logic/dates.py` — `days_until()`, `next_occurrence()` | Important dates job |
| `db/queries/calendar.py` — `get_events_in_range()` | Conflict alerts job |
| `db/supabase.py` — `get_supabase_admin()` | All job functions |
| `providers/llm/openrouter.py` — `get_llm_provider()` | Briefing and dinner suggestion jobs |
| `api/middleware/auth.py` — `get_current_user` | New API routes |
| Supabase `notifications` table | All jobs write here; API reads here |

---

## Phase 7 Preview

Phase 7 — Voice: ElevenLabs Scribe for STT, ElevenLabs TTS for responses,
server-side proxy routes `/api/listen` and `/api/speak`. Mic state management
and barge-in handling on the frontend. No new agent code needed — voice is a
transport layer over the existing Manager Agent.
