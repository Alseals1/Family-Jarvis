# ADR-003: Calendar Integration is Read-Only in MVP

**Date:** 2026-08-09
**Status:** Accepted
**Deciders:** Orchestrator (per build specification)

---

## Context

JARVIS needs to read family calendars. Write access (creating, modifying, deleting events) is technically possible but introduces significant risk.

## Decision

Calendar access is **read-only** in the MVP and all phases until explicit write support is designed, reviewed, and approved.

## Rationale

- Accidental calendar modifications are high-impact and hard to reverse
- Read-only OAuth scope (`https://www.googleapis.com/auth/calendar.readonly`) is safer
- MVP goal is intelligence and conversation — not automation
- Write access requires confirmation UI that doesn't exist yet

## Consequences

- JARVIS cannot create reminders in Google Calendar (MVP)
- JARVIS cannot block time or schedule events (MVP)
- Calendar write support is a future feature requiring its own approval gate

## Implementation Notes

- Google OAuth scope: `calendar.readonly`
- Backend never attempts any write to calendar providers
- Future write feature will require: confirmation dialog + audit log + explicit opt-in
