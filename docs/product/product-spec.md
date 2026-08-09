# Family JARVIS — Product Specification

**Version:** 0.1 (Planning)
**Status:** Pre-implementation — awaiting architecture approval
**Last updated:** 2026-08-09

---

## 1. Product Vision

Family JARVIS is an AI-powered family chief of staff that helps a family coordinate their lives by combining calendars, important dates, preferences, meals, trips, reminders, and plans into one conversational assistant.

The primary experience should feel like talking to a capable family chief of staff — not using a chatbot or calendar search box.

JARVIS should:
- Notice things before the family asks
- Understand context across conversations
- Be trustworthy (never invent, never act autonomously)
- Be proactive without being intrusive

---

## 2. Primary User

A parent or household manager who:
- Coordinates schedules for multiple family members
- Plans meals, date nights, and trips
- Wants to stay ahead of important dates and conflicts
- Needs one intelligent view of the family's life

Access via:
- iPad (primary)
- iPhone
- Desktop browser
- Voice

---

## 3. Core Capabilities

### Conversational Interface
- Natural language conversation
- Context preserved across turns (minimum last 10 turns)
- Pronoun and reference resolution ("Why?" / "What about the second one?")
- Concise, useful responses — not verbose summaries

### Calendar Intelligence
- Aggregate calendars from all family members
- Detect conflicts
- Calculate availability windows
- Identify unusually busy days/weeks
- Identify important dates approaching

### Important Date Awareness
- Birthdays
- Anniversaries
- Trip departures
- School milestones
- Recurring traditions

### Dinner Planning (Chef Agent)
- Consider cooking time available
- Consider food preferences and dietary restrictions
- Consider pantry
- Consider budget
- Avoid recently repeated meals

### Date-Night Planning (Date Planner Agent)
- Find available windows in family calendar
- Consider preferences, history, budget
- Recommend activities and restaurants
- Never book — only recommend

### Proactive Intelligence
- Morning/evening briefings
- Birthday/anniversary reminders
- Conflict alerts
- Free-evening suggestions
- Dinner opportunity prompts
- Trip preparation reminders

### Voice Interaction
- ElevenLabs Scribe (speech-to-text)
- ElevenLabs TTS (text-to-speech)
- Mic disabled while JARVIS speaks

### Family Memory
- Explicit memory only (user-triggered)
- Always confirm what was saved
- Never silently remember

---

## 4. Hard Constraints (Absolute)

| Constraint | Rule |
|---|---|
| Send messages | Never — JARVIS may draft, never send |
| Send calendar invites | Never — until explicit write mode enabled |
| Make purchases | Never |
| Make reservations | Never |
| Invent facts | Never — "I don't know yet." if unavailable |
| Silent memory | Never — always confirm what was saved |
| Calendar writes | Read-only in MVP |
| Real data in demos | Never — use demo family only |

---

## 5. Onboarding Flow

On first launch, JARVIS conducts a conversational interview collecting:

**User profile:** name, role, communication preferences
**Family members:** names, relationships, birthdays
**Important dates:** anniversaries, traditions, recurring events
**Schedules:** calendars, school, sports, work, recurring commitments
**Food preferences:** favorites, dislikes, dietary restrictions, cooking skill, budget, prep time
**Relationship context:** anniversary, date-night preferences, budget, childcare
**Trips:** upcoming travel, preferences

Onboarding must be conversational — not a form.

---

## 6. User Journeys

### Journey 1: "What's happening Friday?"
User → Manager → Organizer → Family Calendar → Conflict check → Availability → Response

### Journey 2: "What should we do Friday night?"
User → Manager → Check calendar → Date Planner → Recommendations → Response

### Journey 3: "What's for dinner?"
User → Manager → Check calendar (available cooking time) → Food preferences → Chef → Recommendation

### Journey 4: Morning briefing (proactive)
Scheduled job → Organizer → Important dates check → Conflict check → Manager summarizes → Notification

### Journey 5: "Remember that we like Italian"
User → Manager → Memory write → Confirm: "Saved: family prefers Italian restaurants"

---

## 7. Demo Mode

`JARVIS_DEMO=true` uses a synthetic family with realistic data.
- Never exposes real family data
- UI must show a visible "DEMO" indicator
- Used for testing all phases before connecting real calendars/data

---

## 8. Accessibility and Platform Requirements

- Touch-first on iPad
- Voice interaction
- Responsive for mobile and desktop
- Installable as PWA
- Push notifications where supported (iOS limitations noted)
- No local AI required — cloud-only architecture
