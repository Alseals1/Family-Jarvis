# Family JARVIS — Development Roadmap

**Status:** Pre-implementation
**Last updated:** 2026-08-09

---

## Phase 0 — Discovery & Planning (CURRENT)
**Goal:** Full architecture, team structure, and documentation before any code.
**Owner:** Orchestrator
**Gate:** User approves architecture and Phase 1 plan

- [x] Repository inspected
- [x] Build specification reviewed
- [x] Agent team defined
- [x] Architecture documented
- [x] Data model documented
- [x] Security model documented
- [x] MVP defined
- [ ] USER APPROVAL REQUIRED

---

## Phase 1 — Foundation
**Goal:** Running skeleton — backend, frontend shell, auth, DB connection, OpenRouter abstraction.
**Owner:** Backend Engineer + Systems Architect
**Gate:** All services connect, auth works, OpenRouter responds, no secrets in browser

Deliverables:
- Repository structure
- Python/FastAPI backend
- React/TypeScript frontend shell
- Environment configuration
- Supabase connection + migrations
- OpenRouter LLM provider abstraction
- JWT/session authentication
- Basic health endpoints
- CI setup (GitHub Actions)

Tests required:
- Backend health check
- Auth flow
- Supabase connection
- OpenRouter call

---

## Phase 2 — Family Brain
**Goal:** Full family data model working in DB with seed data.
**Owner:** Database Architect + Backend Engineer
**Gate:** All entities CRUD, seed data loads, family isolation verified by tests

Deliverables:
- Family members
- Important dates
- Food preferences
- Preferences
- Memories
- Trips
- Relationships
- Demo seed data
- RLS policies

Tests required:
- Family isolation (family A cannot read family B data)
- Important date CRUD
- Preference storage and retrieval

---

## Phase 3 — Calendar Intelligence
**Goal:** Google Calendar connected, conflict detection working, availability calculated.
**Owner:** Integration Engineer + Backend Engineer
**Gate:** Conflict detection tests pass with fixture data before any real calendar is connected

Deliverables:
- CalendarProvider abstraction
- GoogleCalendarProvider
- Event normalization
- Conflict detection (application code, not LLM)
- Availability calculation (application code, not LLM)
- Daily briefing data shape
- Weekly briefing data shape
- Demo calendar fixtures

Tests required:
- Conflict detection (overlapping events)
- All-day event handling
- Recurring event handling
- Timezone correctness
- Availability calculation
- Multi-member scheduling

---

## Phase 4 — Manager Agent (MVP Milestone)
**Goal:** End-to-end conversation working — "What's happening Friday?" answered correctly.
**Owner:** AI/Agent Architect + Backend Engineer
**Gate:** Evaluation scenarios pass; JARVIS never invents; context resolution works

Deliverables:
- Conversation API endpoint
- Manager Agent with OpenRouter
- Context manager (10-turn history)
- Tool routing to Organizer
- Structured agent response protocol
- No-invention guardrail
- Demo conversation flow

Tests required:
- "What's happening Friday?" — correct calendar answer
- "Do we have a conflict?" — correct yes/no
- "What about Saturday?" — correct context resolution
- "When is our anniversary?" — correct from important dates
- "Send my wife a text" — draft only, never send
- Prompt injection via calendar description — treated as content, not instruction

---

## Phase 5 — Specialist Agents
**Goal:** Chef and Date Planner working; Manager delegates to all three specialists.
**Owner:** AI/Agent Architect + Backend Engineer
**Gate:** Each agent tested independently and together; Manager controls all invocation

Deliverables:
- Organizer Agent (formalized from Phase 4)
- Chef Agent
- Date Planner Agent
- Structured agent communication protocol
- Agent evaluation suite

Tests required:
- Chef recommendation with available cooking time
- Chef avoids recently repeated meals
- Date Planner finds availability
- Date Planner considers preferences and history
- Manager correctly routes to correct specialist

---

## Phase 6 — Proactive Intelligence
**Goal:** JARVIS sends proactive alerts without being asked.
**Owner:** Backend Engineer + AI/Agent Architect
**Gate:** Scheduled jobs run, alerts are accurate, no false positives

Deliverables:
- Background job scheduler
- Morning briefing job
- Evening briefing job
- Birthday reminder (14-day window)
- Anniversary reminder (14-day window)
- Trip departure reminder
- Conflict alert
- Free-evening suggestion

Tests required:
- Birthday reminder triggers at correct lead time
- Conflict alert triggers correctly
- No duplicate alerts
- Jobs run on schedule

---

## Phase 7 — Voice
**Goal:** Full voice conversation via ElevenLabs — mic in, JARVIS speaks out.
**Owner:** Voice Engineer
**Gate:** Voice round-trip works; mic never active while JARVIS speaks; keys never in browser

Deliverables:
- `/api/listen` (Scribe STT)
- `/api/speak` (ElevenLabs TTS)
- Mic state management
- Audio playback
- Interrupt handling
- Voice error states

Tests required:
- Key never reaches browser (verified in network inspector)
- Mic disables when JARVIS speaks
- Error states handled visibly

---

## Phase 8 — UI & PWA
**Gate: REQUIRES SCREENSHOT APPROVAL FROM USER BEFORE THIS PHASE**

**Goal:** Production-quality mobile-first UI, installable PWA.
**Owner:** UI/UX Designer + Frontend Engineer
**Gate:** Screenshot provided and visual language approved by user

Deliverables:
- Visual design system (from user screenshot)
- iPad layout
- iPhone layout
- Desktop layout
- PWA manifest
- Service worker
- Install experience
- Push notifications (where iOS allows)

---

## Phase 9 — Production
**Goal:** Deployed to Render/Supabase with full production configuration.
**Owner:** DevOps Engineer + Security Engineer
**Gate:** Security review passed; no secrets exposed; monitoring in place

Deliverables:
- Render deployment (backend + frontend)
- Production Supabase
- HTTPS + custom domain
- Environment secrets
- Structured logging
- Error tracking
- Rate limiting
- Backup strategy
- Recovery procedures
- Load test

---

## Post-MVP (Future Phases)

| Feature | Priority |
|---|---|
| Apple/iCloud Calendar | High |
| Microsoft Outlook Calendar | Medium |
| Grocery list generation | Medium |
| Recipe integration | Low |
| Weather for date-night planning | Low |
| Multi-language support | Low |
| Multiple family units per account | Low |
| Calendar write (with confirmation) | High (v2) |
