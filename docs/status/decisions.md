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

## Decisions Made (2026-08-09 — User Approval Session)

| ID | Decision | Notes |
|---|---|---|
| Q-001 | Architecture APPROVED | Phase 1 may begin |
| Q-002 | Tech stack CONFIRMED | Python/FastAPI + React/TypeScript + Supabase + Render |
| Q-003 | UI visual language APPROVED | Dark near-black, cyan-teal HUD rings, sci-fi. See screenshot: `javisDemo/Screenshot 2026-08-09 at 2.08.19 PM.png` |
| Q-004 | OpenRouter model: `google/gemma-4-31b-it:free` | All agents use this model (free tier) |
| Q-005 | Google Cloud project: needs to be created | Blocker for Phase 3 — not needed for Phase 1 |
| Q-006 | ElevenLabs API key confirmed in .env; German voice requested | `ELEVENLABS_VOICE_ID` still needs German voice ID from ElevenLabs dashboard |
| Q-007 | Production: Render subdomain (no custom domain) | Cheapest/easiest route |

## Workflow Rules Added

- Plan file required in `/plans/` before each phase
- One branch per task, always pushed
- Tests must pass before merge — never modify tests, only code
- All merges go to `dev` only; `main` = production
- Branch only off `dev`
- Do not merge to `dev` without user approval
- Use `pr-recap` skill before every commit/PR

## Open Items

| ID | Item | Urgency |
|---|---|---|
| OI-001 | Set `ELEVENLABS_VOICE_ID` in .env with German voice ID from ElevenLabs dashboard | Before Phase 7 |
| OI-002 | Create Google Cloud project + OAuth credentials | Before Phase 3 |
| OI-003 | Generate `CALENDAR_ENCRYPTION_KEY` (32-byte hex) | Before Phase 3 |
| OI-004 | Generate `JWT_SECRET` (secure random string) | Before Phase 1 runs |

---

## Open Architectural Questions

| ID | Question | Current Assumption |
|---|---|---|
| AQ-001 | Conversation storage: in-memory vs DB? | DB (`conversation_turns` table) for durability |
| AQ-002 | Background job platform: APScheduler vs Supabase Edge Functions? | APScheduler in FastAPI for MVP |
| AQ-003 | Push notifications on iOS PWA? | iOS restricts push for PWAs — will use in-app notifications initially |
| AQ-004 | Calendar sync frequency? | On-demand + 15-min background refresh |
| AQ-005 | OAuth token encryption algorithm? | AES-256-GCM with `CALENDAR_ENCRYPTION_KEY` env var |
