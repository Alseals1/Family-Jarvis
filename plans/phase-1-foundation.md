# Phase 1 — Foundation Plan

**Phase:** 1
**Status:** PLANNED — Awaiting implementation start
**Created:** 2026-08-09
**Orchestrator:** family-jarvis-orchestrator

---

## Goal

Build the project skeleton: a running FastAPI backend, a React/TypeScript frontend shell, Supabase connection, OpenRouter LLM abstraction, and JWT authentication — all wired together, all tested, no visual design yet.

At the end of Phase 1, this must work:
```
curl -X POST http://localhost:8000/api/auth/login → JWT token returned
curl -X GET  http://localhost:8000/health         → { "status": "ok" }
curl -X POST http://localhost:8000/api/llm/test   → OpenRouter responds with a test completion
```

---

## Constraints

- No application features yet — foundation only
- No UI visual design (screenshot gate applies to Phase 8)
- All API keys stay server-side
- `JARVIS_DEMO=true` in development
- Every task has its own branch, branched off `dev`
- No merging to `dev` until tests pass AND user approves
- Use `pr-recap` before every PR

---

## Pre-Phase Setup (one-time, before any branches)

These must be done before any feature branch is created:

| Step | Action | Notes |
|---|---|---|
| S-1 | Initialize git repo in `/Users/aseals/Desktop/ChiefOfStaff` | `git init` |
| S-2 | Create `main` branch (production) | Default git behavior |
| S-3 | Create `dev` branch off `main` | Set as GitHub default branch |
| S-4 | Create `.gitignore` | Must include `.env*`, `node_modules/`, `__pycache__/`, etc. |
| S-5 | Push empty repo to GitHub | User must create repo first or confirm org/name |
| S-6 | Generate `JWT_SECRET` in `.env` | `python -c "import secrets; print(secrets.token_hex(32))"` |

---

## Tasks

### Task 1 — Repository Structure
**Branch:** `feat/repo-structure`
**Branch off:** `dev`
**Owner:** Backend Engineer

Create the monorepo directory layout:
```
/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── agents/
│   │   ├── providers/
│   │   │   ├── llm/
│   │   │   ├── calendar/
│   │   │   └── voice/
│   │   ├── db/
│   │   ├── logic/
│   │   ├── jobs/
│   │   └── models/
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── .env (symlink or copy from root)
├── frontend/
│   └── (Vite scaffold in Task 4)
├── supabase/
│   └── migrations/
├── .gitignore
├── .env.example
├── CLAUDE.md
└── README.md
```

Tests: Directory structure verification (simple existence check)
Done when: PR opens, structure exists, no tests fail.

---

### Task 2 — Backend Scaffold
**Branch:** `feat/backend-scaffold`
**Branch off:** `dev`
**Depends on:** Task 1 merged to dev

Build a minimal FastAPI app that starts and responds:

**Files to create:**
- `backend/app/main.py` — FastAPI app, CORS, middleware mount
- `backend/app/config.py` — Pydantic Settings reading all env vars
- `backend/app/api/routes/health.py` — `GET /health → { status, version, env, demo_mode }`
- `backend/requirements.txt` — fastapi, uvicorn, pydantic-settings, supabase, python-dotenv, httpx, pytest, pytest-asyncio

**Tests:**
- `tests/unit/test_config.py` — config loads from env without error
- `tests/integration/test_health.py` — `/health` returns 200 with correct shape

Done when: `uvicorn app.main:app --reload` starts, health endpoint passes tests.

---

### Task 3 — OpenRouter LLM Abstraction
**Branch:** `feat/openrouter-abstraction`
**Branch off:** `dev`
**Depends on:** Task 2 merged to dev

Build the provider-agnostic LLM layer:

**Files to create:**
- `backend/app/providers/llm/base.py`
  ```python
  class LLMProvider(ABC):
      async def complete(self, messages, model, temperature=0.7) -> str
      async def complete_structured(self, messages, schema, model) -> dict
  ```
- `backend/app/providers/llm/openrouter.py` — OpenRouterProvider implementing base
- `backend/app/api/routes/llm.py` — `POST /api/llm/test` (dev-only route to verify connection)

**Config used:** `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL_*`

**Tests:**
- `tests/unit/test_llm_provider.py` — mock HTTP; verify correct headers sent (Authorization: Bearer), correct base URL, correct model passed
- `tests/integration/test_openrouter.py` — (skipped in CI unless `RUN_LLM_INTEGRATION=true`) real call to OpenRouter with `OPENROUTER_MODEL_FAST`

Done when: Unit tests pass without real API call; integration test optional in CI.

---

### Task 4 — Supabase Connection
**Branch:** `feat/supabase-connection`
**Branch off:** `dev`
**Depends on:** Task 2 merged to dev

Wire up Supabase client:

**Files to create:**
- `backend/app/db/supabase.py` — async Supabase client singleton, initialized from config
- `backend/app/api/routes/health.py` — extend with DB ping check

**Dependencies added:** `supabase` (Python SDK)

**Tests:**
- `tests/unit/test_supabase_client.py` — client initializes with correct URL/key from config
- `tests/integration/test_db_connection.py` — ping Supabase, verify connection (requires real Supabase creds)

Done when: Backend can connect to Supabase and health endpoint shows DB status.

---

### Task 5 — Authentication
**Branch:** `feat/auth`
**Branch off:** `dev`
**Depends on:** Tasks 2 + 4 merged to dev

Build JWT middleware using Supabase Auth:

**Files to create:**
- `backend/app/api/middleware/auth.py` — FastAPI dependency that verifies Supabase JWT, extracts `user_id` and `family_id`
- `backend/app/api/routes/auth.py` — `GET /api/auth/me` (returns current user from JWT)

**Key rule:** `family_id` comes from JWT claims only — never from request body.

**Tests:**
- `tests/unit/test_auth_middleware.py`
  - Valid JWT → user extracted correctly
  - Expired JWT → 401 returned
  - Missing Authorization header → 401 returned
  - JWT with wrong family_id in body → body family_id ignored, JWT family_id used
- `tests/integration/test_auth_flow.py` — full Supabase auth flow (sign up, get token, use token)

Done when: All auth unit tests pass; no route is accessible without valid JWT (except `/health`).

---

### Task 6 — Frontend Shell
**Branch:** `feat/frontend-shell`
**Branch off:** `dev`
**Depends on:** Task 2 merged to dev (independent of backend tasks 3-5)

Scaffold the React/TypeScript frontend — no visual design:

**Setup:**
```
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

**Files to create/configure:**
- `frontend/src/api/client.ts` — axios/fetch wrapper that hits `VITE_API_URL`
- `frontend/src/pages/` — placeholder pages: Home, Onboarding, Chat
- `frontend/src/App.tsx` — basic router (React Router)
- `frontend/.env.example` — `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- `frontend/public/manifest.json` — PWA manifest stub (no icons yet)

**Dependencies:** react-router-dom, @supabase/supabase-js

**Tests:**
- `frontend/src/api/client.test.ts` — API client sends correct base URL
- `frontend/src/App.test.tsx` — renders without crashing

Done when: `npm run dev` starts, no TypeScript errors, basic routing works.

---

### Task 7 — Initial DB Migrations
**Branch:** `feat/db-migrations-initial`
**Branch off:** `dev`
**Depends on:** Task 4 merged to dev

Create first migration set for Phase 1 tables only:

**Migrations to write (`supabase/migrations/`):**
1. `001_create_families.sql` — `families` table
2. `002_create_family_members.sql` — `family_members` table
3. `003_enable_rls.sql` — Enable RLS on both tables + initial policies
4. `004_create_conversations.sql` — `conversations` + `conversation_turns` tables (needed for Phase 4 but schema-only now)

**Seed:** `supabase/seed/demo-family.sql` — "The Reeds" demo family, 4 members, no calendar data yet

**Tests:**
- `tests/integration/test_migrations.py`
  - Migrations apply without error
  - Demo seed loads without error
  - Family A cannot query Family B data (RLS test)
  - `family_id` from JWT is required for all family data access

Done when: All migrations apply cleanly; RLS isolation test passes.

---

### Task 8 — CI Setup
**Branch:** `feat/ci-setup`
**Branch off:** `dev`
**Depends on:** Tasks 1-7

Create GitHub Actions CI pipeline:

**File:** `.github/workflows/ci.yml`

Runs on: every push to any branch, every PR to `dev`

Steps:
1. Python 3.11
2. `pip install -r backend/requirements.txt`
3. `pytest backend/tests/unit/ -v` (no integration tests in CI — they need real creds)
4. Node 20
5. `cd frontend && npm ci && npm run build && npm test`

**Tests:** CI itself is the test — must pass green.

Done when: CI runs green on a test push.

---

## Merge Order

```
dev (base)
 ├── feat/repo-structure          → PR → dev (first)
 ├── feat/backend-scaffold        → PR → dev (after repo-structure)
 ├── feat/openrouter-abstraction  → PR → dev (after backend-scaffold)
 ├── feat/supabase-connection     → PR → dev (after backend-scaffold, parallel with openrouter)
 ├── feat/auth                    → PR → dev (after supabase-connection)
 ├── feat/frontend-shell          → PR → dev (after backend-scaffold, parallel track)
 ├── feat/db-migrations-initial   → PR → dev (after supabase-connection)
 └── feat/ci-setup                → PR → dev (last — after all above)
```

Tasks 3 (OpenRouter) and 4 (Supabase) can run in parallel after Task 2.
Task 6 (Frontend) can run in parallel after Task 2.

---

## Phase 1 Definition of Done

- [ ] `git init` complete, `dev` set as default branch on GitHub
- [ ] `.gitignore` protects `.env*` and build artifacts
- [ ] `GET /health` returns 200 with `status: ok`, DB status, and demo mode flag
- [ ] OpenRouter responds to a test completion (unit tested with mocks)
- [ ] Supabase connection verified
- [ ] JWT auth middleware tested — valid/invalid/expired/missing all handled
- [ ] `/api/auth/me` returns current user from JWT
- [ ] Frontend shell runs (`npm run dev`), no TypeScript errors, basic routing works
- [ ] Initial migrations apply cleanly
- [ ] Demo family seed loads
- [ ] RLS isolation test passes (Family A cannot read Family B)
- [ ] All unit tests pass (`pytest backend/tests/unit/`)
- [ ] Frontend builds without errors
- [ ] CI runs green
- [ ] No API keys in frontend code or git history
- [ ] User approves merge of all Phase 1 branches to `dev`

---

## Open Items Before Phase 1 Starts

| Item | Owner | Blocking |
|---|---|---|
| Create GitHub repo (confirm name + org) | User | S-5 |
| Generate `JWT_SECRET` in `.env` | User | Task 5 |
| Confirm `VITE_SUPABASE_ANON_KEY` in `frontend/.env` | User | Task 6 |

---

## Next Phase Preview

Phase 2 — Family Brain: Full data model, all 16 entities, seed data, complete RLS, family member CRUD.
