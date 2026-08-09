# Phase 3 — Calendar Intelligence Plan

**Phase:** 3
**Status:** PLANNED — awaiting implementation start
**Created:** 2026-08-09
**Depends on:** Phase 2 complete (79/79 tests passing, 14 migrations applied, family isolation proven)
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Build the calendar intelligence layer: the CalendarProvider abstraction, Google Calendar OAuth integration, event normalization into Supabase, and all deterministic calendar logic (conflict detection, availability calculation, upcoming-date summarization). No LLM is used for any of this — it is pure Python.

**Phase 3 is complete when:**
```
GET /api/calendar/events?start=2026-08-09&end=2026-08-16
→ {
    "events": [...normalized CalendarEvent objects...],
    "conflicts": [{"time": "...", "members": [...], "event_a": "...", "event_b": "..."}],
    "availability": [{"member": "...", "windows": [...]}]
  }
```
And: conflict detection catches the Saturday 10am conflict seeded in the demo family. Availability correctly identifies the free Friday evening. All logic is tested with fixture data — no real Google Calendar call is required for tests to pass.

---

## What Is Being Built

### 1. CalendarProvider abstraction
`backend/app/providers/calendar/base.py` — the abstract interface that all calendar providers implement. Google Calendar is the only implementation in Phase 3. The abstraction exists so Apple and Outlook providers can be added later without touching application logic.

### 2. GoogleCalendarProvider
`backend/app/providers/calendar/google.py` — reads events from Google Calendar API using a stored OAuth refresh token. Normalizes Google's event format into a shared `CalendarEvent` dataclass. Never writes to the calendar.

### 3. Google OAuth flow
`backend/app/api/routes/calendar.py` — two endpoints that handle the Google OAuth handshake. On completion, the refresh token is encrypted and stored in the `calendars` table. The token is never returned to the frontend.

### 4. Token encryption
`backend/app/providers/calendar/encryption.py` — symmetric encryption/decryption for OAuth refresh tokens at rest. Uses `CALENDAR_ENCRYPTION_KEY` from environment (already in `config.py` and `.env.example`).

### 5. Event normalization
`backend/app/providers/calendar/normalizer.py` — converts provider-specific event shapes into a uniform `CalendarEvent` dataclass. Google event → normalized event. This is the contract that all downstream logic depends on.

### 6. Calendar sync
`backend/app/db/queries/calendar.py` — upsert normalized events into `calendar_events` table, keyed on `external_id + calendar_id`. Handles stale-cache detection. Sync triggers on user request; background sync is a Phase 7 concern.

### 7. Conflict detection — `logic/conflicts.py`
Pure Python. No LLM. Accepts a list of normalized events for a family, groups by time overlap, returns conflict records. Rules:
- Two events conflict when their intervals overlap AND they involve different members who share the same required-at-home constraint, OR any single member has two simultaneous events.
- All-day events do not conflict with time-bounded events.
- Cancelled events are excluded.

### 8. Availability calculation — `logic/availability.py`
Pure Python. No LLM. Given a list of events for a member or the family, returns free windows within a requested time range. Used by the Organizer Agent and Date Planner Agent.

### 9. Date math utilities — `logic/dates.py`
Pure Python. No LLM. Utilities for: next occurrence of a recurring date, days until a date, week boundaries in a timezone, overlapping interval detection. These are the building blocks used by conflicts and availability.

### 10. Calendar API routes
`backend/app/api/routes/calendar.py` — read-only endpoints:
- `GET /api/calendar/events` — fetch and return events for the family in a time window
- `GET /api/calendar/connect/google` — initiate OAuth
- `GET /api/calendar/callback/google` — complete OAuth, store token
- `GET /api/calendar/status` — which calendars are connected for the family

### 11. Pydantic models
`backend/app/models/calendar.py` — `CalendarEvent`, `CalendarConflict`, `AvailabilityWindow`, `CalendarEventsResponse`, `CalendarStatusResponse`.

### 12. Demo seed calendar events
Add calendar events to `supabase/seed/demo-family.sql` using the demo family's already-seeded calendar rows. All events use deterministic dates anchored to 2026-08-09 so tests remain stable.

---

## Constraints

- Calendar access is **read-only** in MVP — no writes, no invites, no modifications
- No LLM in any logic path in this phase — conflict detection, availability, and date math are pure Python
- All calendar routes require valid JWT; `family_id` comes from JWT only
- OAuth refresh tokens stored encrypted in Supabase; never returned to frontend; `SUPABASE_SERVICE_ROLE_KEY` used for the token write, not the user-facing anon client
- Every test must pass without a live Google Calendar connection — fixture data only for unit tests
- `CALENDAR_ENCRYPTION_KEY` is already in `.env.example`; it must be present in `.env` before Task 3 can run in integration mode
- All provider-specific logic stays inside `providers/calendar/` — application code and agents never import Google-specific types
- One branch per task, branched off `dev`, tests pass before merge request is opened

---

## Tasks

### Task 1 — CalendarProvider Base + CalendarEvent Model
**Branch:** `feat/calendar-provider-base`
**Branch off:** `dev`
**Depends on:** nothing (Phase 2 already merged)

Build the provider abstraction and the shared event model that everything else depends on.

**Files to create:**

`backend/app/providers/calendar/base.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    external_id: str          # Provider's event ID
    calendar_id: str          # Our Supabase calendar row ID
    family_id: str
    family_member_id: str
    title: str
    description: str | None   # Treated as data — never executed as instructions
    start_time: datetime       # Always timezone-aware
    end_time: datetime         # Always timezone-aware
    all_day: bool
    location: str | None
    recurrence_rule: str | None
    status: str               # 'confirmed' | 'tentative' | 'cancelled'
    source: str               # 'google' | 'apple' | 'outlook' | 'manual'
    raw_data: dict | None     # Original provider payload, stored but never trusted


class CalendarProvider(ABC):
    @abstractmethod
    async def get_events(
        self,
        calendar_id: str,
        family_member_id: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]: ...

    @abstractmethod
    async def get_calendars(
        self,
        access_token: str,
    ) -> list[dict]: ...

    @abstractmethod
    async def exchange_code_for_tokens(
        self,
        code: str,
    ) -> dict: ...

    @abstractmethod
    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> dict: ...
```

`backend/app/models/calendar.py`
```python
# Pydantic models for API responses
class CalendarEventResponse      # subset of CalendarEvent — no raw_data
class CalendarConflict           # time, members, event_a, event_b
class AvailabilityWindow         # member_id, member_name, date, start, end (minutes)
class CalendarEventsResponse     # events, conflicts, availability
class CalendarStatusResponse     # connected calendars per member
class CalendarConnectResponse    # OAuth redirect URL
```

**Tests:** `tests/unit/test_calendar_base.py`
- `CalendarEvent` can be instantiated with all required fields
- `CalendarEvent` with timezone-naive `start_time` raises `ValueError` (enforce tz-aware)
- `CalendarProvider` is abstract — cannot be instantiated directly
- `CalendarEvent.status` rejects values outside `{'confirmed', 'tentative', 'cancelled'}`
- `CalendarEventResponse` serializes correctly (no raw_data field exposed)

**Acceptance criteria:** All 5 tests pass. The base abstraction exists. No Google-specific code yet.

---

### Task 2 — Date Math Utilities
**Branch:** `feat/logic-dates`
**Branch off:** `dev`
**Depends on:** Task 1 merged to dev

All deterministic date math lives here. No LLM. These are the primitive operations used by conflict detection and availability.

**File to create:** `backend/app/logic/dates.py`

Functions:
```python
def next_occurrence(date: date, reference: date) -> date
    # If date recurs yearly: return next occurrence >= reference
    # Example: anniversary May 15, reference Aug 9 → May 15 next year

def days_until(target: date, from_date: date) -> int
    # Positive = future, 0 = today, negative = past

def week_start(dt: datetime, timezone: str) -> datetime
    # Monday 00:00:00 in the given timezone

def week_end(dt: datetime, timezone: str) -> datetime
    # Sunday 23:59:59 in the given timezone

def intervals_overlap(
    start_a: datetime, end_a: datetime,
    start_b: datetime, end_b: datetime,
) -> bool
    # True if the two half-open intervals [start_a, end_a) and [start_b, end_b) overlap
    # All inputs must be timezone-aware

def to_family_timezone(dt: datetime, timezone: str) -> datetime
    # Convert a UTC datetime to the family's local timezone

def parse_date_range(start_str: str, end_str: str) -> tuple[datetime, datetime]
    # Parse ISO date strings from query params into tz-aware datetimes
    # Raises ValueError on bad input — never silently coerces
```

**Tests:** `tests/unit/test_logic_dates.py`
- `next_occurrence`: anniversary before today → returns next year; anniversary after today → returns this year
- `days_until`: today → 0; yesterday → -1; tomorrow → 1
- `intervals_overlap`: non-overlapping; adjacent (touching, not overlapping); overlapping by 1 minute; fully contained; identical; reversed (end < start) raises ValueError
- `week_start` / `week_end`: correct for Monday-based week in America/New_York
- `to_family_timezone`: UTC → America/Chicago correct offset
- `parse_date_range`: valid ISO string → correct datetime pair; invalid string → ValueError

**Target:** 15+ test cases. All deterministic — no mocking needed.

**Acceptance criteria:** All tests pass. No imports from providers or agents. No LLM calls.

---

### Task 3 — Conflict Detection
**Branch:** `feat/logic-conflicts`
**Branch off:** `dev`
**Depends on:** Tasks 1 + 2 merged to dev

**File to create:** `backend/app/logic/conflicts.py`

```python
from app.providers.calendar.base import CalendarEvent
from app.models.calendar import CalendarConflict

def detect_conflicts(events: list[CalendarEvent]) -> list[CalendarConflict]:
    """
    Given a flat list of CalendarEvent objects (for all family members,
    already filtered to a time window), return every conflicting pair.

    Rules:
    - A conflict = two events whose intervals overlap where the same member
      has both events simultaneously (cannot be in two places at once)
    - All-day events do NOT conflict with time-bounded events
    - Cancelled events are excluded entirely
    - Duplicate external_ids are deduplicated before detection
    - Returns [] if no conflicts found
    """
```

The function returns a list of `CalendarConflict` objects, each containing:
- `conflict_time`: the start of the overlapping window
- `member_id` and `member_name`: whose schedule conflicts
- `event_a_title` and `event_b_title`: the two events
- `overlap_minutes`: how long the overlap lasts

**Tests:** `tests/unit/test_logic_conflicts.py`

Use fixture events built from `CalendarEvent` dataclass directly (no DB, no HTTP).

Test cases:
1. `test_no_events_returns_empty` — empty input → empty list
2. `test_non_overlapping_events_no_conflict` — 9am-10am and 11am-12pm same member → no conflict
3. `test_adjacent_events_no_conflict` — 9am-10am and 10am-11am → no conflict (touching, not overlapping)
4. `test_overlapping_same_member_is_conflict` — 9am-11am and 10am-12pm same member → conflict detected
5. `test_overlapping_different_members_no_conflict` — same time, different members → no conflict
6. `test_all_day_does_not_conflict_with_timed_event` — all_day=True alongside a 10am meeting → no conflict
7. `test_cancelled_events_excluded` — status='cancelled' events never appear in conflicts
8. `test_exact_overlap_at_saturday_10am` — reproduce the Reeds demo scenario: Marcus has soccer 10am-11am, Priya has doctor 10am-11:30am → no conflict (different members, correctly)
9. `test_marcus_double_booked` — Marcus has two overlapping events → conflict returned
10. `test_conflict_contains_correct_member_name` — conflict object names the correct member
11. `test_deduplication_of_same_external_id` — same event ID appearing twice → treated as one event

**Acceptance criteria:** 11 tests pass. No LLM calls. Saturday 10am scenario correctly handled (family-level view has no conflict because different members; individual-member double-booking correctly flagged).

Note on the Saturday scenario: two different family members at the same time is a scheduling awareness item (the Organizer Agent surfaces it), not a conflict in the same-person-double-booked sense. The conflict detector flags same-member overlaps. The Organizer Agent's briefing logic handles cross-member schedule awareness separately.

---

### Task 4 — Availability Calculation
**Branch:** `feat/logic-availability`
**Branch off:** `dev`
**Depends on:** Tasks 1 + 2 merged to dev (parallel with Task 3)

**File to create:** `backend/app/logic/availability.py`

```python
from app.providers.calendar.base import CalendarEvent
from app.models.calendar import AvailabilityWindow

def get_availability(
    events: list[CalendarEvent],
    family_member_id: str,
    date_range_start: datetime,
    date_range_end: datetime,
    min_window_minutes: int = 30,
    day_start_hour: int = 8,
    day_end_hour: int = 22,
) -> list[AvailabilityWindow]:
    """
    Given events for a single member, return free windows within the
    date range where there are no confirmed or tentative events.
    - Windows shorter than min_window_minutes are not returned
    - Only hours between day_start_hour and day_end_hour are considered
    - Cancelled events are ignored
    - All-day events block the entire day
    """

def get_family_availability(
    events: list[CalendarEvent],
    member_ids: list[str],
    date_range_start: datetime,
    date_range_end: datetime,
    min_window_minutes: int = 60,
) -> list[AvailabilityWindow]:
    """
    Intersect availability across all listed members.
    Returns windows where ALL members are free simultaneously.
    """
```

**Tests:** `tests/unit/test_logic_availability.py`

1. `test_empty_events_entire_day_available` — no events → full day from day_start to day_end available
2. `test_event_at_9am_blocks_9am_window` — 9am event → 8am-9am window and 10am+ window returned, not 9am-10am
3. `test_all_day_event_blocks_full_day` — all_day event → no windows for that day
4. `test_cancelled_events_do_not_block` — status='cancelled' → treated as free
5. `test_window_shorter_than_minimum_excluded` — 20-minute gap with min=30 → not returned
6. `test_free_friday_evening` — seed scenario: no events after 6pm on Friday → 6pm-10pm window returned
7. `test_family_availability_intersection` — member A free 6-8pm, member B free 5-7pm → intersection is 6-7pm
8. `test_family_availability_no_intersection` — members never free at same time → empty result
9. `test_day_boundary_respected` — events outside day_start/day_end hours ignored for windowing
10. `test_back_to_back_events_no_gap` — events from 9am-12pm and 12pm-3pm → no window between them

**Acceptance criteria:** 10 tests pass. No LLM calls. The free-Friday-evening test validates the demo scenario.

---

### Task 5 — Token Encryption
**Branch:** `feat/calendar-token-encryption`
**Branch off:** `dev`
**Depends on:** Task 1 merged to dev (independent of Tasks 2-4)

OAuth refresh tokens must be encrypted at rest. This is a security primitive that the Google provider and OAuth routes depend on.

**File to create:** `backend/app/providers/calendar/encryption.py`

```python
def encrypt_token(plaintext: str, key: str) -> str
    # Fernet symmetric encryption
    # key = CALENDAR_ENCRYPTION_KEY (hex string → bytes)
    # Returns base64-encoded ciphertext safe for TEXT column storage

def decrypt_token(ciphertext: str, key: str) -> str
    # Inverse of encrypt_token
    # Raises ValueError on bad key or corrupted ciphertext

def is_valid_key(key: str) -> bool
    # Returns True if key is a valid 32-byte hex string
    # Used in startup health check
```

Uses: `cryptography` library (Fernet). Add `cryptography` to `requirements.txt`.

**Tests:** `tests/unit/test_token_encryption.py`
1. `test_encrypt_decrypt_roundtrip` — encrypt then decrypt returns original string
2. `test_different_plaintext_different_ciphertext` — same key, different inputs → different outputs
3. `test_wrong_key_raises_error` — decrypting with wrong key raises ValueError
4. `test_corrupted_ciphertext_raises_error` — tampered ciphertext raises ValueError
5. `test_valid_key_check` — 32-byte hex string passes; 16-byte hex fails; non-hex fails
6. `test_empty_string_encrypts_correctly` — edge case: empty string roundtrips

**Acceptance criteria:** 6 tests pass. `cryptography` added to `requirements.txt`. Key never logged.

---

### Task 6 — Event Normalizer
**Branch:** `feat/calendar-normalizer`
**Branch off:** `dev`
**Depends on:** Task 1 merged to dev

The normalizer converts raw Google Calendar API responses into `CalendarEvent` dataclass instances. This is the boundary layer — all Google-specific field names are contained here.

**File to create:** `backend/app/providers/calendar/normalizer.py`

```python
from app.providers.calendar.base import CalendarEvent

def normalize_google_event(
    raw_event: dict,
    calendar_id: str,
    family_id: str,
    family_member_id: str,
) -> CalendarEvent | None:
    """
    Convert a Google Calendar API event dict to a CalendarEvent.
    Returns None if the event should be skipped (e.g., declined invites).

    Google-specific handling:
    - 'dateTime' vs 'date' fields (timed vs all-day)
    - 'timeZone' on start/end (may differ from calendar timezone)
    - 'status' mapping: 'confirmed' → 'confirmed', 'tentative' → 'tentative',
      'cancelled' → 'cancelled'
    - 'attendees' self-RSVP 'declined' → return None (skip)
    - 'summary' → title (empty summary becomes 'Untitled Event')
    - 'description' stored as-is — NOT sanitized for instructions (prompt injection
      defense is at the agent layer, not here)
    - Always produces timezone-aware datetimes in UTC
    """
```

**Tests:** `tests/unit/test_calendar_normalizer.py`

Use fixture dicts that match the real Google Calendar API response shape (no HTTP call needed).

1. `test_timed_event_normalizes_correctly` — standard event with dateTime start/end
2. `test_all_day_event_sets_all_day_true` — event with `date` field (not `dateTime`)
3. `test_timezone_aware_output` — output start_time is always tz-aware
4. `test_declined_invite_returns_none` — attendee with self=true and responseStatus=declined → None
5. `test_empty_summary_becomes_untitled` — missing or empty summary → 'Untitled Event'
6. `test_cancelled_status_preserved` — Google status 'cancelled' → CalendarEvent status 'cancelled'
7. `test_description_stored_verbatim` — description with injection attempt stored exactly, not sanitized
8. `test_external_id_is_google_event_id` — CalendarEvent.external_id = raw_event['id']
9. `test_missing_end_time_raises` — malformed event with no end → ValueError, not None

**Acceptance criteria:** 9 tests pass. Google-specific field names only appear in this file. Output is always a `CalendarEvent` or `None`.

---

### Task 7 — GoogleCalendarProvider
**Branch:** `feat/google-calendar-provider`
**Branch off:** `dev`
**Depends on:** Tasks 1, 5, 6 merged to dev

Implement the Google Calendar API client. This is the only file that knows about Google's API. It implements `CalendarProvider`.

**File to create:** `backend/app/providers/calendar/google.py`

```python
class GoogleCalendarProvider(CalendarProvider):
    """
    Implements CalendarProvider for Google Calendar API v3.
    Read-only. Never writes events, never sends invites.

    Token management:
    - Receives decrypted access_token for API calls
    - Detects 401 responses → triggers token refresh via refresh_token
    - After refresh: caller (calendar routes) stores new encrypted token
    - Never stores tokens in memory beyond the request lifecycle
    """

    BASE_URL = "https://www.googleapis.com/calendar/v3"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    async def get_events(
        self,
        calendar_id: str,         # Google calendar ID (e.g., 'primary' or specific calendar)
        family_member_id: str,    # For annotating CalendarEvent objects
        start: datetime,
        end: datetime,
        access_token: str,        # Decrypted, caller manages lifecycle
    ) -> list[CalendarEvent]: ...

    async def get_calendars(
        self,
        access_token: str,
    ) -> list[dict]: ...

    async def exchange_code_for_tokens(
        self, code: str
    ) -> dict: ...                # Returns {access_token, refresh_token, expiry}

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict: ...                # Returns {access_token, expiry}

    def build_oauth_url(self, state: str) -> str: ...
```

Dependencies: `httpx` (already in requirements), `google-auth` not required (we implement the OAuth flow directly using httpx — no heavy Google SDK).

**Tests:** `tests/unit/test_google_calendar_provider.py`

All HTTP calls mocked with `unittest.mock` or `pytest-mock`.

1. `test_get_events_calls_correct_url` — verifies the correct Google API endpoint is called with the right parameters
2. `test_get_events_uses_access_token_in_header` — `Authorization: Bearer <token>` header present
3. `test_get_events_normalizes_response` — raw Google response → list of CalendarEvent objects
4. `test_get_events_empty_response` — Google returns no items → empty list, no error
5. `test_get_calendars_lists_calendar_ids` — returns list with at least 'primary'
6. `test_exchange_code_returns_token_dict` — code exchange returns expected keys
7. `test_refresh_token_returns_new_access_token` — refresh endpoint called, new token returned
8. `test_401_response_raises_token_expired_error` — custom exception so caller can retry with refresh
9. `test_build_oauth_url_contains_required_scopes` — URL includes `calendar.readonly` scope
10. `test_no_write_scope_in_oauth_url` — `calendar` (write) scope must NOT be present

**Acceptance criteria:** 10 tests pass. No real Google API called. Read-only scopes enforced. `calendar.readonly` is the only calendar scope requested.

---

### Task 8 — Calendar DB Queries
**Branch:** `feat/calendar-db-queries`
**Branch off:** `dev`
**Depends on:** Tasks 1, 5 merged to dev

Build the Supabase query layer for calendar data. Application code and agents call this — they never write SQL directly.

**File to create:** `backend/app/db/queries/calendar.py`

```python
async def get_calendars_for_family(
    family_id: str,
    db: SupabaseClient,
) -> list[dict]:
    # Returns calendar rows for the family (no token columns)
    # Token columns excluded from query SELECT

async def get_decrypted_tokens(
    calendar_id: str,
    db_admin: SupabaseClient,  # service role — bypasses RLS
) -> tuple[str, str, datetime]:
    # Returns (access_token_plain, refresh_token_plain, expiry)
    # Admin client required — tokens not visible via RLS
    # Used only by backend sync logic, never user-facing routes

async def upsert_calendar_events(
    events: list[CalendarEvent],
    db_admin: SupabaseClient,
) -> int:
    # Upsert events into calendar_events table
    # Key: (calendar_id, external_id)
    # Returns count of rows upserted
    # Admin client because user anon client cannot write

async def get_events_in_range(
    family_id: str,
    start: datetime,
    end: datetime,
    db: SupabaseClient,
) -> list[dict]:
    # Query calendar_events within time window for family
    # Returns raw dicts — caller converts to CalendarEvent

async def store_calendar_connection(
    family_id: str,
    family_member_id: str,
    provider: str,
    external_id: str,
    name: str,
    access_token_enc: str,
    refresh_token_enc: str,
    token_expiry: datetime,
    db_admin: SupabaseClient,
) -> str:
    # Creates or updates a calendar row
    # Returns the calendar's UUID

async def update_token(
    calendar_id: str,
    access_token_enc: str,
    token_expiry: datetime,
    db_admin: SupabaseClient,
) -> None:
    # Called after a token refresh — updates access token only

async def mark_calendar_synced(
    calendar_id: str,
    db_admin: SupabaseClient,
) -> None:
    # Updates last_synced_at = now()
```

**Tests:** `tests/unit/test_calendar_db_queries.py`

Mock the Supabase client (`MagicMock`). Verify query structure, not DB results.

1. `test_get_calendars_excludes_token_columns` — SELECT does not include `access_token_enc` or `refresh_token_enc`
2. `test_get_decrypted_tokens_uses_admin_client` — uses `db_admin`, not `db`
3. `test_upsert_uses_admin_client` — upsert uses `db_admin`, not user-facing client
4. `test_get_events_in_range_filters_by_family_id` — query includes `family_id` filter
5. `test_get_events_in_range_filters_by_time` — query includes `gte(start)` and `lte(end)` on `start_time`
6. `test_store_calendar_connection_passes_encrypted_tokens` — raw plaintext not stored
7. `test_update_token_does_not_touch_refresh_token` — only access_token_enc and expiry updated

**Acceptance criteria:** 7 tests pass. Token columns never appear in user-facing queries. Admin client used for all write operations.

---

### Task 9 — Calendar API Routes
**Branch:** `feat/calendar-routes`
**Branch off:** `dev`
**Depends on:** Tasks 1, 5, 6, 7, 8 merged to dev

Wire up the HTTP endpoints. These are the routes the frontend and Organizer Agent consume.

**File to create:** `backend/app/api/routes/calendar.py`

```
GET  /api/calendar/status
     → CalendarStatusResponse: which calendars connected per family member

GET  /api/calendar/connect/google
     → CalendarConnectResponse: { "oauth_url": "https://accounts.google.com/..." }
     Generates state param (UUID), stores in-memory for CSRF validation

GET  /api/calendar/callback/google?code=...&state=...
     → Validates state (CSRF), exchanges code for tokens, encrypts tokens,
       calls get_calendars to list the user's Google calendars,
       stores each in Supabase via store_calendar_connection
     → Returns { "connected": true, "calendars": [...] }

GET  /api/calendar/events?start=YYYY-MM-DD&end=YYYY-MM-DD
     → Queries Supabase for events in range (uses cached data)
     → Runs conflict detection (logic/conflicts.py)
     → Runs availability calculation (logic/availability.py)
     → Returns CalendarEventsResponse
     → If no calendar connected: returns { "events": [], "conflicts": [],
       "availability": [], "message": "No calendar connected" }

POST /api/calendar/sync
     → Triggers a fresh pull from Google Calendar for all connected calendars
     → Upserts results into Supabase
     → Returns { "synced": N } where N = events upserted
     → Rate-limited: one sync per family per 5 minutes (returns 429 if too soon)
```

**Security rules enforced in routes:**
- All routes require JWT; `family_id` from JWT only
- OAuth `state` param validated against server-side value — mismatch → 400
- Token columns never returned in any response
- `POST /api/calendar/sync` uses admin client for DB writes; user client for reads

**Tests:** `tests/unit/test_calendar_routes.py`

Mock all DB calls and provider calls. Test route logic and security rules.

1. `test_status_returns_connected_calendars` — returns list of connected calendars with no token data
2. `test_connect_returns_oauth_url` — URL is a valid Google OAuth URL with correct scopes
3. `test_callback_missing_state_returns_400` — missing or wrong state → 400
4. `test_callback_success_stores_encrypted_token` — after OAuth complete, encrypted token in DB
5. `test_events_returns_correct_shape` — response has events, conflicts, availability keys
6. `test_events_no_calendar_connected_returns_empty` — graceful empty response, not 500
7. `test_events_conflict_detection_called` — logic.conflicts.detect_conflicts invoked with events
8. `test_sync_calls_google_provider` — POST /sync triggers GoogleCalendarProvider.get_events
9. `test_sync_rate_limit_respected` — second sync within 5 min → 429
10. `test_events_family_id_from_jwt_not_query_param` — passing `family_id` as query param is ignored

**Acceptance criteria:** 10 tests pass. All security rules verified in tests. No Google API called in tests.

---

### Task 10 — Calendar Seed Events + Integration Verification
**Branch:** `feat/calendar-seed-events`
**Branch off:** `dev`
**Depends on:** Tasks 1-9 merged to dev (this is the validation task)

Add calendar events to the demo seed and write tests that prove the full logic chain works end-to-end using only fixture data.

**Changes to:** `supabase/seed/demo-family.sql`

Add a `calendars` row for each Reeds family member:
- Marcus Reed → primary Google calendar
- Priya Reed → primary Google calendar
- Eli Reed → manual calendar (child, no Google account)
- Zoe Reed → manual calendar (child, no Google account)

Add `calendar_events` rows for the week of 2026-08-09 to 2026-08-16:

| Date | Member | Title | Start | End | Notes |
|---|---|---|---|---|---|
| Mon Aug 10 | Marcus | Work standup | 09:00 | 09:30 | |
| Mon Aug 10 | Priya | Client call | 14:00 | 15:00 | |
| Tue Aug 11 | Eli | Soccer practice | 16:00 | 17:30 | |
| Tue Aug 11 | Zoe | Dance class | 16:00 | 17:00 | |
| Wed Aug 12 | Marcus | Doctor appointment | 10:00 | 11:00 | |
| Thu Aug 13 | Priya | Work presentation | 13:00 | 14:00 | |
| Fri Aug 14 | (none) | Free evening | — | — | Verified by absence |
| Sat Aug 15 | Marcus | Soccer | 10:00 | 11:00 | Cross-member awareness scenario |
| Sat Aug 15 | Priya | Dentist | 10:00 | 11:30 | Cross-member awareness scenario |
| Sun Aug 16 | Marcus | Marcus double-booked | 14:00 | 15:00 | Conflict test |
| Sun Aug 16 | Marcus | Marcus double-booked 2 | 14:30 | 15:30 | Conflict test |

All events use `status = 'confirmed'`, `source = 'manual'` for seed (provider sync is Phase 7's background job concern).

**New test file:** `tests/unit/test_calendar_logic_integration.py`

This file pulls events from the seed SQL (parsed, not executed against a DB) and runs them through the full logic chain. It is the highest-value test in Phase 3.

1. `test_marcus_double_booking_sunday_detected` — Sunday double-booking → conflict detected
2. `test_saturday_cross_member_no_same_person_conflict` — Marcus + Priya both at 10am → no same-person conflict (different members)
3. `test_free_friday_evening_identified` — no events on Friday after 18:00 → availability window returned
4. `test_week_summary_has_correct_event_count` — 11 events total in the week
5. `test_cancelled_event_excluded_from_count` — add a cancelled event to fixtures; count stays 11
6. `test_family_availability_friday_evening` — all 4 members free after 18:00 Friday → family window returned
7. `test_event_normalization_in_seed_consistent` — all seed events have tz-aware times in UTC

**Also add to existing `tests/unit/test_demo_seed.py`:**
- `test_calendars_present_for_all_members` — seed contains calendar row for each of 4 members
- `test_calendar_events_present` — at least 10 calendar events in seed
- `test_double_booking_event_present` — Marcus has two Sunday events with overlapping times

**Acceptance criteria:** 7 new integration logic tests pass. 3 new seed tests pass. End-to-end: load fixtures → run conflict detection → run availability → correct results. No DB, no HTTP, no LLM.

---

## Merge Order

```
dev (base, Phase 2 merged)
 │
 ├── Task 1: feat/calendar-provider-base         (no deps — start first)
 │
 ├── Task 5: feat/calendar-token-encryption      (after T1, parallel with T2-T4)
 ├── Task 6: feat/calendar-normalizer            (after T1, parallel with T2-T5)
 │
 ├── Task 2: feat/logic-dates                    (after T1)
 ├── Task 3: feat/logic-conflicts                (after T1 + T2)
 ├── Task 4: feat/logic-availability             (after T1 + T2, parallel with T3)
 │
 ├── Task 7: feat/google-calendar-provider       (after T1 + T5 + T6)
 ├── Task 8: feat/calendar-db-queries            (after T1 + T5)
 │
 ├── Task 9: feat/calendar-routes                (after T1 + T5 + T6 + T7 + T8)
 │
 └── Task 10: feat/calendar-seed-events          (after T1-T9 all merged — last)
```

Parallelizable groups:
- After Task 1: Tasks 2, 5, and 6 can all start simultaneously
- After Task 2: Tasks 3 and 4 can run in parallel
- After Tasks 1 + 5 + 6: Tasks 7 and 8 can run in parallel

---

## New Files Summary

| File | Task |
|---|---|
| `backend/app/providers/calendar/base.py` | T1 |
| `backend/app/models/calendar.py` | T1 |
| `backend/app/logic/dates.py` | T2 |
| `backend/app/logic/conflicts.py` | T3 |
| `backend/app/logic/availability.py` | T4 |
| `backend/app/providers/calendar/encryption.py` | T5 |
| `backend/app/providers/calendar/normalizer.py` | T6 |
| `backend/app/providers/calendar/google.py` | T7 |
| `backend/app/db/queries/calendar.py` | T8 |
| `backend/app/api/routes/calendar.py` | T9 |
| `supabase/seed/demo-family.sql` (extended) | T10 |
| `tests/unit/test_calendar_base.py` | T1 |
| `tests/unit/test_logic_dates.py` | T2 |
| `tests/unit/test_logic_conflicts.py` | T3 |
| `tests/unit/test_logic_availability.py` | T4 |
| `tests/unit/test_token_encryption.py` | T5 |
| `tests/unit/test_calendar_normalizer.py` | T6 |
| `tests/unit/test_google_calendar_provider.py` | T7 |
| `tests/unit/test_calendar_db_queries.py` | T8 |
| `tests/unit/test_calendar_routes.py` | T9 |
| `tests/unit/test_calendar_logic_integration.py` | T10 |

**Modified files:**
- `backend/requirements.txt` — add `cryptography` (T5)
- `backend/app/main.py` — register calendar router (T9)
- `supabase/seed/demo-family.sql` — add calendars + calendar_events (T10)
- `tests/unit/test_demo_seed.py` — add 3 new assertions (T10)

---

## Phase 3 Definition of Done

- [ ] `CalendarProvider` abstract base exists; `GoogleCalendarProvider` implements it fully
- [ ] `CalendarEvent` dataclass always produces timezone-aware datetimes
- [ ] `logic/dates.py` — all 15+ date math tests pass
- [ ] `logic/conflicts.py` — 11 tests pass; same-member overlap detected; different-member same-time correctly not flagged as a double-booking conflict
- [ ] `logic/availability.py` — 10 tests pass; free Friday evening identified from fixture data
- [ ] Token encryption — 6 tests pass; wrong key raises error; empty string roundtrips
- [ ] Normalizer — 9 tests pass; declined invites return None; injection-attempt description stored verbatim
- [ ] GoogleCalendarProvider — 10 tests pass; only `calendar.readonly` scope requested; no write scope
- [ ] Calendar DB queries — 7 tests pass; token columns excluded from user-facing SELECT; admin client used for writes
- [ ] Calendar routes — 10 tests pass; OAuth state CSRF validated; family_id from JWT only; sync rate-limited
- [ ] Seed extended — 4 calendar rows (one per member), 11+ calendar_events; double-booking scenario present
- [ ] Integration logic tests — 7 tests pass; end-to-end fixture → detect_conflicts → get_availability → correct result
- [ ] Demo seed assertions — 3 new seed tests pass
- [ ] All existing 79 tests still pass (no regressions)
- [ ] Total unit test count: 79 + ~92 new = 171+ passing
- [ ] `cryptography` added to `requirements.txt`
- [ ] `calendar` router registered in `backend/app/main.py`
- [ ] No LLM calls in any `logic/` or `providers/calendar/` file
- [ ] No Google API secrets exposed in test output or logs
- [ ] No calendar write scopes requested in OAuth flow
- [ ] User approves merge of all Phase 3 branches to `dev`

---

## Dependencies on Phase 1 and 2 Deliverables

| Phase 2 deliverable | How Phase 3 uses it |
|---|---|
| `calendars` table (migration 005) | `store_calendar_connection` writes here; OAuth callback creates rows |
| `calendar_events` table (migration 006) | All calendar data lives here; `get_events_in_range` queries this |
| `014_rls_phase2.sql` — RLS on `calendar_events` | User-facing queries auto-scoped to family; admin client bypasses for writes |
| `app/api/middleware/auth.py` — `family_id` from JWT | Calendar routes use `get_current_user()` — no change needed |
| `app/db/supabase.py` — client singleton | `calendar.py` queries import this |
| `app/config.py` — `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `CALENDAR_ENCRYPTION_KEY` | All present from Phase 1; Phase 3 actively uses them |
| Demo seed — `families`, `family_members` rows for The Reeds | Task 10 seed adds `calendars` + `calendar_events` rows that FK to these |

---

## Pre-Phase 3 Checklist

These must be confirmed before the first branch is opened:

| Item | Owner | Blocking |
|---|---|---|
| `GOOGLE_CLIENT_ID` set in `.env` | User | Task 7 integration test (optional) |
| `GOOGLE_CLIENT_SECRET` set in `.env` | User | Task 7 integration test (optional) |
| `GOOGLE_REDIRECT_URI` confirmed for local dev | User | Task 9 OAuth callback |
| `CALENDAR_ENCRYPTION_KEY` generated in `.env` | User | Task 5 |
| All Phase 2 branches merged to `dev` | Confirmed via git log | Task 1 |

Note: Unit tests for Tasks 1-9 require none of the above — they all mock external dependencies. Only the optional integration tests (skipped in CI unless `RUN_CALENDAR_INTEGRATION=true`) require real credentials.

---

## Phase 4 Preview

Phase 4 — Manager Agent: The conversational Manager Agent is built on top of the calendar intelligence established here. The Organizer Agent will call `get_events_in_range` + `detect_conflicts` + `get_availability` to answer questions like "What's happening Friday?" and "Do we have any conflicts this week?" All the logic is already deterministic Python by that point — Phase 4's job is to wrap it in natural-language understanding and response generation.
