# Family JARVIS

An AI-powered family chief of staff that helps coordinate schedules, meals, date nights, important dates, and family life — through natural conversation.

**Status:** Planning phase — not yet implemented.

---

## What It Does

- **Calendar Intelligence** — Aggregates family calendars, detects conflicts, calculates availability
- **Important Date Awareness** — Birthdays, anniversaries, trips, traditions
- **Dinner Planning** — Considers cooking time, preferences, pantry, budget
- **Date Night Planning** — Finds available evenings, recommends based on history and preferences
- **Proactive Alerts** — Notices things before you ask: conflicts, approaching dates, free evenings
- **Natural Conversation** — Context preserved across turns; understands follow-up questions
- **Voice Interaction** — Speak to JARVIS, JARVIS speaks back (ElevenLabs)
- **iPad/Mobile PWA** — Installable, touch-optimized, works offline for static assets

---

## Architecture

```
iPad / iPhone / Desktop
        |
        HTTPS
        |
Python/FastAPI Backend (Render)
        |
  ┌─────┴──────┐
  OpenRouter   ElevenLabs
  (LLM)        (Voice)
        |
     Supabase
     (PostgreSQL + Auth)
```

Agents:
- **Manager** — Coordinates everything, speaks to user
- **Organizer** — Calendar intelligence
- **Chef** — Dinner recommendations
- **Date Planner** — Date-night recommendations

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / FastAPI |
| Frontend | React / TypeScript |
| Database | Supabase / PostgreSQL |
| AI | OpenRouter (model-agnostic gateway) |
| Voice | ElevenLabs (Scribe + TTS) |
| Calendar | Google Calendar (MVP), Apple/Outlook (future) |
| Hosting | Render |

---

## Development Setup

**Prerequisites:** Python 3.11+, Node 18+, Supabase account, OpenRouter account

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in values
3. Install backend: `cd backend && pip install -r requirements.txt`
4. Install frontend: `cd frontend && npm install`
5. Run Supabase migrations: see `docs/database/data-model.md`
6. Start backend: `cd backend && uvicorn app.main:app --reload`
7. Start frontend: `cd frontend && npm run dev`

Full setup guide: coming in Phase 1 (`docs/setup.md`)

---

## Documentation

| Document | Location |
|---|---|
| Product Specification | `docs/product/product-spec.md` |
| MVP Definition | `docs/product/mvp.md` |
| Development Roadmap | `docs/product/roadmap.md` |
| System Architecture | `docs/architecture/architecture.md` |
| Agent Architecture | `docs/architecture/agent-architecture.md` |
| Data Model | `docs/database/data-model.md` |
| Security Model | `docs/security/security-model.md` |
| Team Structure | `docs/agents/team-structure.md` |
| Current Status | `docs/status/current-state.md` |

---

## Safety Rules

JARVIS never:
- Sends emails, texts, or messages without explicit confirmation
- Creates or modifies calendar events (MVP: read-only)
- Makes purchases, reservations, or bookings
- Invents events, people, dates, or facts
- Silently saves memories (always confirms what was saved)

---

## Demo Mode

Set `JARVIS_DEMO=true` to run with synthetic family data. Never test against real family data before demo mode is verified.
