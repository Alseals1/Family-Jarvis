# Family JARVIS — System Architecture

**Version:** 0.1 (Planning)
**Status:** Awaiting approval
**Last updated:** 2026-08-09

---

## 1. Architecture Overview

```
iPad / iPhone / Desktop
         |
         | HTTPS
         v
   ┌─────────────┐
   │  React PWA  │  (Render static)
   └──────┬──────┘
          │ REST / WebSocket
          v
   ┌─────────────────────────────────────────┐
   │           Python / FastAPI              │
   │                                         │
   │  ┌──────────────────────────────────┐  │
   │  │         Manager Agent            │  │
   │  └────────────┬───────────┬─────────┘  │
   │               │           │            │
   │     ┌─────────┘     ┌─────┘            │
   │     v               v                  │
   │  Organizer        Chef / Date Planner  │
   │     │                                  │
   │     v                                  │
   │  Family Brain (Supabase queries)        │
   │                                         │
   └──────────┬─────────────────────────────┘
              │
     ┌────────┴────────┐
     │                 │
     v                 v
  OpenRouter       ElevenLabs
  (LLM Gateway)   (Voice)
     │
     v
  Supabase
  (PostgreSQL + Auth + RLS)
```

---

## 2. Service Responsibilities

### Frontend (React/TypeScript)
- Conversational UI
- Voice recording (sends audio to backend)
- Audio playback (receives audio from backend)
- Calendar display
- Family dashboard
- Onboarding flow
- PWA manifest + service worker
- **Never holds API keys**
- **Never calls OpenRouter or ElevenLabs directly**

### Backend (Python/FastAPI)
- All AI orchestration
- All external API calls (OpenRouter, ElevenLabs, Google Calendar)
- Authentication verification
- Family isolation enforcement
- Session/conversation management
- Background jobs (proactive intelligence)
- Structured logging
- Rate limiting

### Supabase
- PostgreSQL database
- User authentication (Supabase Auth)
- Row-level security (RLS) for family isolation
- Storage (future: voice recordings, family photos)

### OpenRouter
- LLM gateway — all model calls route through here
- Abstracted behind `LLMProvider` interface
- Model configurable per agent via environment variables
- Never called from frontend

### ElevenLabs
- Scribe: Speech-to-text (backend receives audio, returns transcript)
- TTS: Text-to-speech (backend receives text, returns audio)
- Never called from frontend
- Backend proxy endpoints: `/api/listen` and `/api/speak`

---

## 3. LLM Provider Abstraction

The system must never be directly coupled to any single model provider.

```python
class LLMProvider:
    async def complete(self, messages, model, temperature) -> str: ...
    async def complete_structured(self, messages, schema, model) -> dict: ...

class OpenRouterProvider(LLMProvider):
    # Uses OPENROUTER_API_KEY from environment
    # Uses OPENROUTER_BASE_URL
    pass
```

Model configuration via environment variables:

```
OPENROUTER_MODEL_MANAGER=anthropic/claude-3.5-sonnet
OPENROUTER_MODEL_ORGANIZER=anthropic/claude-3-haiku
OPENROUTER_MODEL_CHEF=anthropic/claude-3-haiku
OPENROUTER_MODEL_PLANNER=anthropic/claude-3.5-sonnet
OPENROUTER_MODEL_FAST=anthropic/claude-3-haiku
```

Stronger models for reasoning; faster/cheaper models for extraction and routing.

---

## 4. Calendar Provider Abstraction

```python
class CalendarProvider:
    async def get_events(self, family_member_id, start, end) -> list[CalendarEvent]: ...
    async def get_calendars(self, family_member_id) -> list[Calendar]: ...

class GoogleCalendarProvider(CalendarProvider):
    # OAuth2, refresh token stored in Supabase (encrypted)
    pass

# Future:
class AppleCalendarProvider(CalendarProvider): ...
class OutlookCalendarProvider(CalendarProvider): ...
```

---

## 5. Agent Architecture

See `docs/architecture/agent-architecture.md` for full agent design.

```
User
 │
 ▼
Manager Agent          ← only agent that speaks to user
 │
 ├──► Organizer Agent  ← calendar intelligence
 │         └──► CalendarProvider
 │         └──► Supabase (family, events, important dates)
 │
 ├──► Chef Agent       ← dinner recommendations
 │         └──► Supabase (food_preferences, pantry, recipes)
 │
 └──► Date Planner Agent  ← date-night recommendations
           └──► Supabase (date_history, preferences)
```

Rules:
- Manager is the only agent that communicates with the user
- Specialists receive structured input, return structured output
- No uncontrolled agent-to-agent conversation
- All tool calls through Manager coordination

---

## 6. Authentication

- Supabase Auth (email/password + OAuth)
- JWT tokens
- All backend routes require valid JWT
- Family ID extracted from JWT claims — not from request body
- Frontend never passes family_id in requests (prevents spoofing)

Google Calendar OAuth flow:
- User initiates via frontend
- Backend completes OAuth handshake
- Refresh token encrypted and stored in Supabase
- Never exposed to frontend

---

## 7. Data Flow: "What's happening Friday?"

```
1. User types/speaks → Frontend
2. Frontend POST /api/chat { message: "What's happening Friday?" }
3. Backend: Manager Agent receives message
4. Manager: Determines calendar query needed
5. Manager: Calls Organizer with structured task
   { task: "get_events", date_range: { start: "Friday", end: "Friday" } }
6. Organizer: Queries Supabase (calendar_events for family)
7. Organizer: Optionally fetches from Google Calendar (if stale)
8. Organizer: Runs conflict detection (Python code, no LLM)
9. Organizer: Returns structured result
   { events: [...], conflicts: [...], availability: [...] }
10. Manager: Formats natural-language response via LLM
11. Backend: Returns { response: "Friday you have..." }
12. Frontend: Displays response
13. (If voice enabled) Backend: /api/speak → ElevenLabs → audio
```

---

## 8. Background Jobs

Proactive intelligence runs on a schedule:

| Job | Schedule | Trigger |
|---|---|---|
| Morning briefing | 7:00 AM family timezone | Calendar + important dates |
| Evening briefing | 6:00 PM family timezone | Availability + dinner window |
| Birthday check | Daily | 14-day lookahead |
| Anniversary check | Daily | 14-day lookahead |
| Trip departure check | Daily | 7-day lookahead |
| Conflict alert | On calendar sync | Real-time |

Implementation: APScheduler (FastAPI) or Supabase Edge Functions (future)

---

## 9. Deployment Architecture

**Development:** Local (backend + frontend, Supabase local or cloud)
**Production:** Render (backend + frontend static) + Supabase cloud

```
DNS → Render
  → /api/* → FastAPI service
  → /* → React static build

Secrets: Render environment variables
Database: Supabase (managed PostgreSQL)
```

---

## 10. Cost Control

| Operation | Use LLM? | Reason |
|---|---|---|
| Conflict detection | No | Deterministic logic |
| Date comparison | No | Python datetime |
| Availability calculation | No | Set operations |
| Sorting events | No | sort() |
| Counting events | No | len() |
| Natural language understanding | Yes | Core LLM job |
| Recommendations | Yes | Core LLM job |
| Summarization | Yes | Core LLM job |
| Planning | Yes | Core LLM job |

---

## 11. Security Boundaries

See `docs/security/security-model.md` for full detail.

- No API keys in frontend code or browser environment
- No secrets in git
- Family isolation via RLS (not just application logic)
- External content (calendar descriptions, emails) treated as data, never instructions
- OAuth tokens encrypted at rest
- All logging excludes sensitive content

---

## 12. Technology Decisions

| Component | Choice | Rationale |
|---|---|---|
| Backend language | Python | LLM ecosystem, rapid iteration |
| Backend framework | FastAPI | Async, typed, modern |
| Frontend framework | React + TypeScript | PWA support, component model |
| Database | Supabase/PostgreSQL | RLS built-in, auth built-in, managed |
| LLM gateway | OpenRouter | Provider-agnostic, cost controls |
| Voice STT | ElevenLabs Scribe | Accuracy, same provider as TTS |
| Voice TTS | ElevenLabs | Quality, natural voice |
| Calendar (MVP) | Google Calendar | Largest user base |
| Hosting | Render | Simple, managed, portable |

All technology decisions are recorded as ADRs in `docs/architecture/decisions/`.
