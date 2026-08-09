# ADR-002: Use Supabase for Database and Authentication

**Date:** 2026-08-09
**Status:** Accepted
**Deciders:** Orchestrator (per build specification)

---

## Context

The system needs a database, authentication, and family-level data isolation. Building these from scratch adds significant complexity and security risk.

## Decision

Use Supabase for:
- PostgreSQL database (managed)
- User authentication (Supabase Auth)
- Row-level security (RLS) for family data isolation
- Future: Storage for media

## Rationale

- Managed PostgreSQL removes operational overhead
- Supabase Auth provides JWT-based auth out of the box
- RLS is enforced at the database layer — cannot be bypassed by application bugs
- Supabase local development tools allow offline development
- Portability: Supabase is standard PostgreSQL — can migrate to raw Postgres if needed

## Consequences

- Family isolation enforced at DB layer (good — defense in depth)
- RLS policies must be written and tested carefully
- SUPABASE_SERVICE_ROLE_KEY bypasses RLS — must never reach browser

## Implementation Notes

- `SUPABASE_ANON_KEY`: safe for frontend (subject to RLS)
- `SUPABASE_SERVICE_ROLE_KEY`: backend only — bypasses RLS for admin operations
- All family data queries include `family_id` filter (belt + suspenders with RLS)
