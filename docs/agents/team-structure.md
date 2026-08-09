# Family JARVIS — Agent Team Structure

**Version:** 0.1 (Planning)
**Status:** Awaiting approval
**Last updated:** 2026-08-09

---

## 1. Team Overview

```
┌──────────────────────────────────────┐
│     family-jarvis-orchestrator       │  ← You are here (Principal Orchestrator)
│     Owns: entire project             │
└──────────────────────────────────────┘
              │ coordinates
    ┌─────────┴──────────────────────┐
    │    Planning Tier               │
    │  product-architect             │
    │  systems-architect             │
    │  database-architect            │
    └──────────────┬─────────────────┘
                   │ produces contracts
    ┌──────────────┴─────────────────┐
    │    Implementation Tier         │
    │  backend-engineer              │
    │  frontend-engineer             │
    │  ai-agent-architect            │
    │  voice-engineer                │
    │  integration-engineer          │
    └──────────────┬─────────────────┘
                   │ produces work
    ┌──────────────┴─────────────────┐
    │    QA / Security / Ops Tier    │
    │  security-engineer             │
    │  qa-engineer                   │
    │  devops-engineer               │
    └──────────────┬─────────────────┘
                   │ produces reports
    ┌──────────────┴─────────────────┐
    │    Documentation               │
    │  technical-writer              │
    └────────────────────────────────┘
```

---

## 2. Agent Roster

### family-jarvis-orchestrator (Principal)
**File:** `.claude/agents/orchestrator.md`
**Status:** Active — fully defined
**Role:** Owns the entire project. Coordinates all agents. Sets phase gates. Reviews all work.
**Reports to:** User
**Manages:** All agents below

---

### product-architect
**File:** `.claude/agents/product-architect.md`
**Status:** Stub — needs full definition
**Role:** Define and maintain product requirements, user journeys, acceptance criteria, MVP boundaries, roadmap.
**Reports to:** Orchestrator
**Produces:**
- `docs/product/product-spec.md`
- `docs/product/mvp.md`
- `docs/product/roadmap.md`
- Acceptance criteria per feature
**Can parallelize with:** Systems Architect (after spec is complete)

---

### systems-architect
**File:** `.claude/agents/systems-architect.md`
**Status:** Stub — needs full definition
**Role:** Define overall architecture, service boundaries, API contracts, data flows, integration design.
**Reports to:** Orchestrator
**Depends on:** Product Architect (requires spec before architecture)
**Produces:**
- `docs/architecture/architecture.md`
- `docs/architecture/system-design.md`
- `docs/architecture/api-design.md`
- `docs/architecture/decisions/ADR-*.md`
**Can parallelize with:** Database Architect (after architecture is approved)

---

### database-architect
**File:** `.claude/agents/database-architect.md`
**Status:** Stub — needs full definition
**Role:** Design and maintain Supabase/PostgreSQL schema, RLS policies, indexes, migrations, family isolation.
**Reports to:** Systems Architect (for schema reviews), Orchestrator
**Depends on:** Systems Architect (requires architecture before schema)
**Produces:**
- `docs/database/data-model.md`
- `supabase/migrations/*.sql`
- `docs/database/rls.md`
**Can parallelize with:** Backend Engineer (after schema is approved)

---

### backend-engineer
**File:** `.claude/agents/backend-engineer.md`
**Status:** Stub — needs full definition
**Role:** Implement Python/FastAPI backend, API routes, business logic, authentication, agent execution.
**Reports to:** Orchestrator
**Depends on:** Systems Architect (API design), Database Architect (schema)
**Must consult:** Security Engineer before implementing auth, OAuth, or data exposure
**Produces:**
- `backend/` (entire backend codebase)
- Unit + integration tests

---

### frontend-engineer
**File:** `.claude/agents/frontend-engineer.md`
**Status:** Stub — needs full definition
**Role:** Implement React/TypeScript frontend, API integration, PWA, responsive layouts.
**Reports to:** Orchestrator
**Depends on:** Systems Architect (API contracts), UI/UX Designer (after screenshot gate)
**UI GATE:** Must not implement visual design until screenshot approval received
**Produces:**
- `frontend/` (entire frontend codebase)
- PWA manifest + service worker

---

### ui-ux-designer
**File:** `.claude/agents/ui-ux-designer.md`
**Status:** Stub — needs full definition
**Role:** Information architecture, interaction design, visual system (after screenshot gate).
**Reports to:** Orchestrator
**GATE:** Cannot begin visual design until user provides a screenshot
**Ask the user:** "Send me a screenshot of an interface whose look you want — a dashboard, an app, anything."
**Produces:**
- Visual language description
- Component specifications
- Layout definitions for iPad / iPhone / Desktop

---

### ai-agent-architect
**File:** `.claude/agents/ai-agent-architect.md`
**Status:** Stub — needs full definition
**Role:** Design and implement Manager, Organizer, Chef, Date Planner agents. Prompts, tool definitions, communication protocol, evaluation suite.
**Reports to:** Orchestrator
**Depends on:** Systems Architect (architecture), Database Architect (data model)
**Produces:**
- `backend/app/agents/*.py`
- `docs/agents/` definitions
- Evaluation scenarios

---

### voice-engineer
**File:** `.claude/agents/voice-engineer.md`
**Status:** Stub — needs full definition
**Role:** Implement ElevenLabs Scribe (STT) and TTS, mic state, audio state, interruption handling.
**Reports to:** Orchestrator
**Depends on:** Backend Engineer (API routes for voice), Frontend Engineer (UI hooks)
**Phase:** Phase 7 — not MVP
**Produces:**
- `backend/app/providers/voice/elevenlabs.py`
- `/api/listen` and `/api/speak` routes
- Frontend voice state management

---

### integration-engineer
**File:** `.claude/agents/integration-engineer.md`
**Status:** Stub — needs full definition
**Role:** Google Calendar OAuth + sync. Calendar provider abstraction. Future: Apple, Outlook.
**Reports to:** Orchestrator
**Depends on:** Database Architect (calendars/calendar_events schema), Security Engineer (OAuth security)
**Produces:**
- `backend/app/providers/calendar/*.py`
- OAuth flow implementation
- Calendar sync logic

---

### security-engineer
**File:** `.claude/agents/security-engineer.md`
**Status:** Stub — needs full definition
**Role:** Security review, threat modeling, RLS verification, OAuth security, secrets management, prompt injection defense.
**Reports to:** Orchestrator
**Reviews:** All authentication code, all OAuth code, all external data handling, all logging
**Gate role:** Security review required before each phase is closed
**Produces:**
- `docs/security/security-model.md`
- Security review reports per phase

---

### qa-engineer
**File:** `.claude/agents/qa-engineer.md`
**Status:** Stub — needs full definition
**Role:** Unit tests, integration tests, E2E tests, agent evaluations, regression testing.
**Reports to:** Orchestrator
**Gate role:** Tests must pass before phase is closed
**High-risk areas:** Conflict detection, timezone handling, family isolation, guardrails
**Produces:**
- `backend/tests/`
- `frontend/tests/`
- Evaluation reports

---

### devops-engineer
**File:** `.claude/agents/devops-engineer.md`
**Status:** Stub — needs full definition
**Role:** Render deployment, environment variables, CI/CD, monitoring, logging, backups.
**Reports to:** Orchestrator
**Phase:** Phase 9 (production)
**Produces:**
- `Dockerfile`s
- GitHub Actions CI
- Render configuration
- Production environment setup

---

### technical-writer
**File:** `.claude/agents/technical-writer.md`
**Status:** Stub — needs full definition
**Role:** Maintain README, docs, setup guides, architecture docs, deployment docs.
**Reports to:** Orchestrator
**Rule:** Only documents what actually exists — never documents imaginary features as complete
**Produces:**
- `README.md`
- `docs/` (all documentation)
- Setup guide
- Troubleshooting guide

---

## 3. Communication Protocol

All agent handoffs use structured task contracts:

```
TASK:
OBJECTIVE:
CONTEXT:
DEPENDENCIES:
INPUTS:
OUTPUTS:
DECISIONS:
RISKS:
TESTS:
BLOCKERS:
NEXT ACTION:
```

No informal agent-to-agent conversation. All communication through artifacts in `docs/`.

---

## 4. Parallel Work Map

```
Phase 0 (NOW):       Orchestrator only
                         │
Phase 1:             Backend Eng + Systems Arch (sequential: arch → impl)
                     Database Arch (parallel with Backend after schema done)
                         │
Phase 2:             Database Arch + Backend Eng (parallel)
                     QA starts writing fixtures
                         │
Phase 3:             Integration Eng + Backend Eng (parallel)
                     QA writes calendar tests
                         │
Phase 4:             AI Agent Arch + Backend Eng (parallel)
                     QA writes evaluation scenarios
                         │
Phase 5:             AI Agent Arch (Chef + Date Planner)
                     Backend Eng (routes + integration)
                         │
Phase 6:             Backend Eng (jobs)
                     QA (job tests)
                         │
Phase 7 (UI Gate):   UI/UX Designer + Frontend Eng
                     ← BLOCKED until screenshot received
                         │
Phase 8:             Voice Eng + Frontend Eng (parallel)
                         │
Phase 9:             DevOps + Security Eng (parallel review)
                     Technical Writer (final docs)
```

---

## 5. Phase Gate Approvals

| Gate | Condition | Approver |
|---|---|---|
| Architecture → Phase 1 | User approves architecture | User |
| Phase 1 → Phase 2 | Tests pass, auth works, services connect | Orchestrator |
| Phase 2 → Phase 3 | Family isolation verified, seed data loads | Orchestrator |
| Phase 3 → Phase 4 | Conflict detection tests pass with fixture data | Orchestrator |
| Phase 4 → Phase 5 | MVP evaluation scenarios pass | Orchestrator + User |
| Phase 5 → Phase 6 | All specialist agents tested independently + together | Orchestrator |
| Pre-Phase 8 | UI gate: screenshot received from user | User |
| Phase 9 | Security review passed | Security Engineer + Orchestrator |
| Production | Full definition of done satisfied | User |
