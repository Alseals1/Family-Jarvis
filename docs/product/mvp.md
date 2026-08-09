# Family JARVIS — MVP Definition

**Status:** Pre-implementation — awaiting approval
**Last updated:** 2026-08-09

---

## MVP Goal

Prove the core experience with the smallest viable implementation:

> A family member can ask "What's happening Friday?" and receive a correct, contextual answer drawn from real calendar data, with conflict and availability awareness.

---

## MVP Scope

### Included in MVP

| Feature | Why |
|---|---|
| User authentication | Required for all data access |
| Family setup (manual) | Minimum family context |
| Family members (manual entry) | No calendar without members |
| Important dates (manual entry) | Core awareness feature |
| Google Calendar read-only | Core calendar intelligence |
| Conflict detection | Core differentiator |
| Availability calculation | Core differentiator |
| Manager Agent | Required for conversation |
| Organizer Agent | Required for calendar intelligence |
| Basic conversation context (10 turns) | Required for follow-up questions |
| OpenRouter LLM abstraction | Required — no direct Anthropic coupling |
| Demo mode with seed data | Required — never test on real data |
| Basic text UI (no visual polish) | Functional first |

### Explicitly Excluded from MVP

| Feature | Phase |
|---|---|
| Chef Agent | Phase 6 |
| Date Planner Agent | Phase 6 |
| Voice (ElevenLabs) | Phase 8 |
| Proactive notifications/briefings | Phase 7 |
| PWA / installable app | Phase 9 |
| Apple/Outlook calendar integrations | Post-MVP |
| Pantry / food preferences | Phase 3 |
| Trip planning | Phase 3 |
| Family memory system | Phase 3 |
| UI visual design | Phase 9 (after screenshot approval) |
| Push notifications | Phase 9 |
| Production deployment | Phase 10 |

---

## MVP Success Criteria

The MVP is complete when:

1. User can create an account and set up a family
2. User can connect a Google Calendar
3. User can ask "What's happening Friday?" and get a correct answer
4. Conflict detection correctly identifies overlapping events
5. User can ask a follow-up question ("What about Saturday?") and JARVIS resolves the context
6. Demo mode works with seed data and is never confused with real data
7. All API keys are server-side only
8. Tests pass for conflict detection and availability logic
9. JARVIS says "I don't know yet" rather than inventing information

---

## MVP Non-Goals

- Visual polish
- Voice
- Proactive intelligence
- All calendar providers
- All specialist agents
- Mobile-optimized layout

---

## Definition of MVP Done

- [ ] Repository structure created
- [ ] Backend running (Python/FastAPI)
- [ ] Frontend shell (React/TypeScript)
- [ ] Supabase connected
- [ ] OpenRouter abstraction working
- [ ] Database schema migrated
- [ ] Authentication working
- [ ] Family + members + important dates CRUD
- [ ] Google Calendar OAuth + read working
- [ ] Conflict detection logic tested
- [ ] Organizer Agent returning structured data
- [ ] Manager Agent routing to Organizer
- [ ] Conversation context (10 turns)
- [ ] "What's happening Friday?" works end-to-end
- [ ] Demo mode with seed data
- [ ] Unit + integration tests passing
- [ ] No secrets in browser or git
