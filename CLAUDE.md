# Family JARVIS — Claude Code Project Guide

## Project Overview

Family JARVIS is an AI-powered family chief of staff. It helps a family coordinate their lives through conversational AI, calendar intelligence, dinner planning, date-night recommendations, and proactive reminders.

**Working directory:** `/Users/aseals/Desktop/ChiefOfStaff`

---

## Current Status

**Phase:** 0 — Discovery & Planning (COMPLETE)
**Next step:** User approves architecture → Phase 1 begins

See `docs/status/current-state.md` for live project state.

---

## Architecture At a Glance

```
Frontend (React/TypeScript PWA)
    ↕ HTTPS
Backend (Python/FastAPI)
    ↕ OpenRouter (LLM), ElevenLabs (Voice), Supabase (DB)

Agent hierarchy:
  Manager Agent (user-facing)
    → Organizer Agent (calendar)
    → Chef Agent (dinner)
    → Date Planner Agent (date nights)
         → Family Brain (Supabase)
```

Full architecture: `docs/architecture/architecture.md`

---

## Key Rules

1. **Do not start implementation until the user approves Phase 1.**
2. **Do not build UI visuals until the user provides a screenshot reference.**
3. **Never expose API keys to the browser.**
4. **Never call OpenRouter, ElevenLabs, or Google Calendar from the frontend.**
5. **All LLM calls go through OpenRouter — never Anthropic directly.**
6. **Conflict detection and date math are Python code, not LLM calls.**
7. **Calendar is read-only in MVP.**
8. **JARVIS never sends messages, makes bookings, or purchases.**
9. **Never test against real family data — use demo mode first.**
10. **Every phase must have passing tests before the next phase begins.**

---

## Specialist Agents

| Agent | File | Status |
|---|---|---|
| Orchestrator | `.claude/agents/orchestrator.md` | ACTIVE |
| Product Architect | `.claude/agents/product-architect.md` | Stub |
| Systems Architect | `.claude/agents/systems-architect.md` | Stub |
| Database Architect | `.claude/agents/database-architect.md` | Stub |
| Backend Engineer | `.claude/agents/backend-engineer.md` | Stub |
| Frontend Engineer | `.claude/agents/frontend-engineer.md` | Stub |
| UI/UX Designer | `.claude/agents/ui-ux-designer.md` | Stub |
| AI/Agent Architect | `.claude/agents/ai-agent-architect.md` | Stub |
| Voice Engineer | `.claude/agents/voice-engineer.md` | Stub |
| Integration Engineer | `.claude/agents/integration-engineer.md` | Stub |
| Security Engineer | `.claude/agents/security-engineer.md` | Stub |
| QA Engineer | `.claude/agents/qa-engineer.md` | Stub |
| DevOps Engineer | `.claude/agents/devops-engineer.md` | Stub |
| Technical Writer | `.claude/agents/technical-writer.md` | Stub |

Stubs must be filled before agents can be invoked.

---

## Documentation Map

```
docs/
├── product/          Product spec, MVP definition, roadmap
├── architecture/     System architecture, agent architecture, ADRs
├── database/         Data model, schema, RLS policies
├── agents/           Team structure, agent responsibilities
├── security/         Security model, threat model
├── status/           Current state, active work, blockers, decisions
├── integrations/     (future) Google Calendar, ElevenLabs integration docs
└── testing/          (future) Test strategy, evaluation scenarios
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in real values. Never commit `.env`.

---

## Development Phases

| Phase | Goal | Gate |
|---|---|---|
| 0 | Discovery & Planning | User approval |
| 1 | Foundation (backend, frontend shell, auth, DB) | Tests pass |
| 2 | Family Brain (data model + seed data) | Family isolation verified |
| 3 | Calendar Intelligence | Conflict tests pass with fixtures |
| 4 | Manager Agent (MVP milestone) | Evaluation scenarios pass |
| 5 | Specialist Agents (Chef, Date Planner) | All agents tested |
| 6 | Proactive Intelligence | Jobs run correctly |
| 7 | Voice | Keys never in browser |
| 8 | UI & PWA (BLOCKED on screenshot) | Screenshot approved |
| 9 | Production Deployment | Security review passed |
