# Family JARVIS — Decision Log

**Updated:** 2026-08-09

---

## Decisions Made (from Build Specification)

| ID | Decision | Rationale | Date |
|---|---|---|---|
| D-001 | Use OpenRouter as LLM gateway | Provider-agnostic; model switchable via env var | Per spec |
| D-002 | Use Supabase for DB and auth | Managed PostgreSQL + RLS + auth in one | Per spec |
| D-003 | Python + FastAPI for backend | LLM ecosystem; async; typed | Per spec |
| D-004 | React + TypeScript for frontend | PWA support; component model | Per spec |
| D-005 | ElevenLabs for voice (STT + TTS) | Quality; single vendor for both | Per spec |
| D-006 | Render for initial hosting | Simple; managed; portable | Per spec |
| D-007 | Google Calendar first | Largest user base; MVP focus | Per spec |
| D-008 | Calendar read-only in MVP | Safety; write needs confirmation UI | Per spec |
| D-009 | Manager is only agent speaking to user | Clean architecture; no multi-agent chatter | Per spec |
| D-010 | Conflict detection in Python, not LLM | Deterministic; faster; cheaper | Per spec |
| D-011 | Demo mode (`JARVIS_DEMO=true`) | Never test on real data | Per spec |
| D-012 | Voice: mic disabled while JARVIS speaks | UX; prevent feedback loop | Per spec |
| D-013 | Memory: always explicit + confirmed | Privacy; trust | Per spec |
| D-014 | No purchases, bookings, or sends | Safety; trust | Per spec |

---

## Decisions Needed From User

| ID | Question | Impact | Urgency |
|---|---|---|---|
| Q-001 | Approve architecture as documented? | Blocks all implementation | IMMEDIATE |
| Q-002 | Confirm tech stack (Python/FastAPI + React/TypeScript + Supabase + Render)? | Blocks Phase 1 | IMMEDIATE |
| Q-003 | Provide screenshot for UI visual language? | Blocks Phase 8 (UI design) | Before Phase 8 |
| Q-004 | Which OpenRouter models to start with? (defaults provided in `.env.example`) | Affects cost and quality | Before Phase 4 |
| Q-005 | Google Calendar OAuth app — do you already have a Google Cloud project? | Needed for integration | Before Phase 3 |
| Q-006 | ElevenLabs account and voice preference? | Needed for voice | Before Phase 7 |
| Q-007 | Custom domain for production? | Needed for deployment | Before Phase 9 |

---

## Open Architectural Questions

| ID | Question | Current Assumption |
|---|---|---|
| AQ-001 | Conversation storage: in-memory vs DB? | DB (`conversation_turns` table) for durability |
| AQ-002 | Background job platform: APScheduler vs Supabase Edge Functions? | APScheduler in FastAPI for MVP |
| AQ-003 | Push notifications on iOS PWA? | iOS restricts push for PWAs — will use in-app notifications initially |
| AQ-004 | Calendar sync frequency? | On-demand + 15-min background refresh |
| AQ-005 | OAuth token encryption algorithm? | AES-256-GCM with `CALENDAR_ENCRYPTION_KEY` env var |
