# Family JARVIS — System Design

**Version:** 0.1 (Planning)
**Status:** Awaiting approval
**Last updated:** 2026-08-09

---

## 1. Repository Structure (Target)

```
family-jarvis/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app entrypoint
│   │   ├── config.py                  # Settings from env vars
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── chat.py            # /api/chat
│   │   │   │   ├── calendar.py        # /api/calendar
│   │   │   │   ├── family.py          # /api/family
│   │   │   │   ├── voice.py           # /api/listen, /api/speak
│   │   │   │   └── auth.py            # /api/auth
│   │   │   └── middleware/
│   │   │       ├── auth.py            # JWT verification
│   │   │       └── logging.py         # Structured logging
│   │   ├── agents/
│   │   │   ├── manager.py             # Manager Agent
│   │   │   ├── organizer.py           # Organizer Agent
│   │   │   ├── chef.py                # Chef Agent
│   │   │   ├── date_planner.py        # Date Planner Agent
│   │   │   └── base.py                # AgentTask, AgentResult dataclasses
│   │   ├── providers/
│   │   │   ├── llm/
│   │   │   │   ├── base.py            # LLMProvider interface
│   │   │   │   └── openrouter.py      # OpenRouterProvider
│   │   │   ├── calendar/
│   │   │   │   ├── base.py            # CalendarProvider interface
│   │   │   │   └── google.py          # GoogleCalendarProvider
│   │   │   └── voice/
│   │   │       └── elevenlabs.py      # ElevenLabsProvider
│   │   ├── db/
│   │   │   ├── supabase.py            # Supabase client
│   │   │   └── queries/               # Family, calendar, preferences queries
│   │   ├── logic/
│   │   │   ├── conflicts.py           # Conflict detection (no LLM)
│   │   │   ├── availability.py        # Availability calculation (no LLM)
│   │   │   └── dates.py               # Date utilities (no LLM)
│   │   ├── jobs/
│   │   │   └── scheduler.py           # Proactive intelligence jobs
│   │   └── models/
│   │       └── schemas.py             # Pydantic models
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/                       # Backend API client
│   │   └── types/
│   ├── public/
│   │   └── manifest.json              # PWA manifest
│   ├── package.json
│   └── Dockerfile
├── supabase/
│   ├── migrations/                    # SQL migrations
│   └── seed/                          # Demo seed data
├── docs/                              # (this directory)
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## 2. API Design

### Chat
```
POST /api/chat
Authorization: Bearer <jwt>
Body: {
  "message": "What's happening Friday?",
  "session_id": "uuid"
}
Response: {
  "response": "Friday you have...",
  "session_id": "uuid",
  "sources": ["calendar", "important_dates"]
}
```

### Voice
```
POST /api/listen
Authorization: Bearer <jwt>
Body: multipart/form-data (audio file)
Response: { "transcript": "What's happening Friday?" }

POST /api/speak
Authorization: Bearer <jwt>
Body: { "text": "Friday you have..." }
Response: audio/mpeg stream
```

### Calendar
```
GET /api/calendar/connect/google
→ Initiates OAuth flow

GET /api/calendar/callback/google
→ Completes OAuth, stores refresh token

GET /api/calendar/events?start=&end=
Authorization: Bearer <jwt>
Response: { "events": [...], "conflicts": [...] }
```

### Family
```
GET  /api/family
POST /api/family/members
GET  /api/family/members
POST /api/family/dates          # Important dates
GET  /api/family/dates
POST /api/family/preferences
```

---

## 3. Environment Variables

All documented in `.env.example`. All required at runtime.

```
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=     # Backend only, never browser

# OpenRouter
OPENROUTER_API_KEY=            # Backend only, never browser
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL_MANAGER=
OPENROUTER_MODEL_ORGANIZER=
OPENROUTER_MODEL_CHEF=
OPENROUTER_MODEL_PLANNER=
OPENROUTER_MODEL_FAST=

# ElevenLabs
ELEVENLABS_API_KEY=            # Backend only, never browser
ELEVENLABS_VOICE_ID=

# Google Calendar OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=          # Backend only, never browser
GOOGLE_REDIRECT_URI=

# Application
APP_ENV=development|production
JARVIS_DEMO=true|false
JWT_SECRET=
CORS_ORIGINS=
```

---

## 4. Data Flow Patterns

### Synchronous (user request)
```
Request → Auth middleware → Route handler → Manager Agent
→ (optional) Specialist Agent → DB queries → LLM call
→ Response ← Manager synthesizes ← Structured result
```

### Asynchronous (background jobs)
```
Scheduler → Job function → DB queries
→ Detect trigger condition → Manager summarizes → Store notification
→ Push to connected client (WebSocket) or store for next session
```

### Calendar sync
```
On user request OR on schedule:
CalendarProvider.get_events() → Normalize → Upsert to Supabase
Conflict detection → Update conflicts table → Alert if new conflicts
```

---

## 5. Session Management

- Session ID generated per conversation (UUID)
- Conversation context stored in memory (Redis in production, dict in dev)
- Last 10 turns retained
- Sessions expire after 24 hours of inactivity
- Family ID always from JWT, never from session data

---

## 6. Observability

Every request produces a structured log:
```json
{
  "request_id": "uuid",
  "family_id": "uuid",
  "user_id": "uuid",
  "route": "/api/chat",
  "agents_invoked": ["manager", "organizer"],
  "llm_model": "anthropic/claude-3.5-sonnet",
  "llm_tokens_in": 1200,
  "llm_tokens_out": 340,
  "latency_ms": 1850,
  "error": null,
  "timestamp": "2026-08-09T..."
}
```

Never logged: API keys, OAuth tokens, message content in production, private family data.
