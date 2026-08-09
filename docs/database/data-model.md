# Family JARVIS — Data Model

**Version:** 0.1 (Planning)
**Status:** Awaiting approval — no migrations run yet
**Last updated:** 2026-08-09

---

## 1. Design Principles

- Every user-owned record has `family_id`
- No global shared data (all family-scoped)
- Row-level security (RLS) enforces family isolation at DB layer
- Application code also filters by family_id (defense in depth)
- Soft deletes preferred (`deleted_at`) for sensitive data

---

## 2. Entity Summary

| Entity | Purpose |
|---|---|
| `families` | Top-level family unit |
| `family_members` | Individual people in the family |
| `calendars` | Calendar connections per member |
| `calendar_events` | Normalized events from all calendar providers |
| `important_dates` | Birthdays, anniversaries, traditions |
| `preferences` | General family and member preferences |
| `food_preferences` | Dietary restrictions, favorites, dislikes |
| `recipes` | Meal suggestions / saved recipes |
| `pantry_items` | Items available at home (future) |
| `trips` | Planned travel |
| `relationships` | Member-to-member relationships (couple, parent-child) |
| `date_history` | Date-night history for Date Planner context |
| `memories` | Explicitly saved family memories |
| `notifications` | Proactive alert queue |
| `agent_tasks` | Background and async agent task log |
| `conversations` | Conversation session metadata |
| `conversation_turns` | Individual turns within a conversation |

---

## 3. Schema Definitions

### families
```sql
CREATE TABLE families (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  timezone    TEXT NOT NULL DEFAULT 'America/New_York',
  demo_mode   BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### family_members
```sql
CREATE TABLE family_members (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id    UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  relationship TEXT NOT NULL,  -- 'adult_partner', 'child', 'extended'
  birthday     DATE,
  email        TEXT,
  active       BOOLEAN NOT NULL DEFAULT true,
  user_id      UUID REFERENCES auth.users(id),  -- if this member has an account
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### calendars
```sql
CREATE TABLE calendars (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id UUID NOT NULL REFERENCES family_members(id) ON DELETE CASCADE,
  provider         TEXT NOT NULL,  -- 'google', 'apple', 'outlook', 'manual'
  external_id      TEXT,           -- Google calendar ID
  name             TEXT NOT NULL,
  color            TEXT,
  sync_enabled     BOOLEAN NOT NULL DEFAULT true,
  last_synced_at   TIMESTAMPTZ,
  -- OAuth tokens encrypted, never returned to frontend
  access_token_enc TEXT,
  refresh_token_enc TEXT,
  token_expiry     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### calendar_events
```sql
CREATE TABLE calendar_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  calendar_id      UUID NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
  family_member_id UUID NOT NULL REFERENCES family_members(id),
  external_id      TEXT,           -- Provider event ID
  title            TEXT NOT NULL,
  description      TEXT,           -- Treated as data, never instructions
  start_time       TIMESTAMPTZ NOT NULL,
  end_time         TIMESTAMPTZ NOT NULL,
  all_day          BOOLEAN NOT NULL DEFAULT false,
  location         TEXT,
  recurrence_rule  TEXT,
  status           TEXT DEFAULT 'confirmed',  -- 'confirmed', 'tentative', 'cancelled'
  source           TEXT NOT NULL,  -- 'google', 'apple', 'manual'
  raw_data         JSONB,          -- Original provider payload
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_calendar_events_family_time ON calendar_events(family_id, start_time, end_time);
CREATE INDEX idx_calendar_events_member ON calendar_events(family_member_id, start_time);
```

### important_dates
```sql
CREATE TABLE important_dates (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id UUID REFERENCES family_members(id),  -- null = whole family
  label            TEXT NOT NULL,  -- 'Birthday', 'Anniversary', 'Trip', 'Tradition'
  date_type        TEXT NOT NULL,  -- 'birthday', 'anniversary', 'trip', 'holiday', 'other'
  date             DATE NOT NULL,
  recurs_yearly    BOOLEAN NOT NULL DEFAULT true,
  notes            TEXT,
  lead_days        INT NOT NULL DEFAULT 14,  -- days before to alert
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_important_dates_family ON important_dates(family_id, date);
```

### preferences
```sql
CREATE TABLE preferences (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id UUID REFERENCES family_members(id),  -- null = family-wide
  category         TEXT NOT NULL,  -- 'general', 'dining', 'activities', 'communication'
  key              TEXT NOT NULL,
  value            JSONB NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(family_id, family_member_id, category, key)
);
```

### food_preferences
```sql
CREATE TABLE food_preferences (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id UUID REFERENCES family_members(id),  -- null = family-wide
  preference_type  TEXT NOT NULL,  -- 'favorite', 'dislike', 'restriction', 'allergy'
  item             TEXT NOT NULL,  -- 'Italian food', 'mushrooms', 'gluten', etc.
  notes            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### memories
```sql
CREATE TABLE memories (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id UUID REFERENCES family_members(id),
  content          TEXT NOT NULL,   -- What was saved
  category         TEXT,            -- 'preference', 'event', 'fact', etc.
  confirmed_to_user BOOLEAN NOT NULL DEFAULT true,  -- Was user told what was saved?
  source           TEXT,            -- 'explicit' only (never silent)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### trips
```sql
CREATE TABLE trips (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  destination      TEXT,
  departure_date   DATE,
  return_date      DATE,
  travelers        UUID[],          -- family_member IDs
  notes            TEXT,
  status           TEXT DEFAULT 'planned',  -- 'planned', 'active', 'completed'
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### relationships
```sql
CREATE TABLE relationships (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  member_a_id      UUID NOT NULL REFERENCES family_members(id),
  member_b_id      UUID NOT NULL REFERENCES family_members(id),
  relationship_type TEXT NOT NULL,  -- 'partners', 'parent_child', 'siblings'
  anniversary_date DATE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### date_history
```sql
CREATE TABLE date_history (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  relationship_id  UUID REFERENCES relationships(id),
  date             DATE NOT NULL,
  activity         TEXT,
  restaurant       TEXT,
  notes            TEXT,
  rating           INT,  -- 1-5
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### notifications
```sql
CREATE TABLE notifications (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  type             TEXT NOT NULL,  -- 'birthday', 'anniversary', 'conflict', 'briefing'
  content          TEXT NOT NULL,
  trigger_date     DATE NOT NULL,
  delivered        BOOLEAN NOT NULL DEFAULT false,
  delivered_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### conversations
```sql
CREATE TABLE conversations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  user_id          UUID NOT NULL REFERENCES auth.users(id),
  session_id       TEXT NOT NULL UNIQUE,
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  turn_count       INT NOT NULL DEFAULT 0
);
```

### conversation_turns
```sql
CREATE TABLE conversation_turns (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  turn_number      INT NOT NULL,
  role             TEXT NOT NULL,  -- 'user' | 'assistant'
  content          TEXT NOT NULL,
  agents_invoked   TEXT[],
  data_sources     TEXT[],
  llm_tokens       INT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### agent_tasks
```sql
CREATE TABLE agent_tasks (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  task_type        TEXT NOT NULL,
  agent            TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'done', 'failed'
  inputs           JSONB,
  outputs          JSONB,
  error            TEXT,
  started_at       TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. Row-Level Security

Every table with `family_id` requires RLS policy:

```sql
-- Example for calendar_events
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "family_members_can_read_own_events"
  ON calendar_events FOR SELECT
  USING (
    family_id IN (
      SELECT family_id FROM family_members
      WHERE user_id = auth.uid()
    )
  );
```

`SUPABASE_SERVICE_ROLE_KEY` bypasses RLS — used only on backend for admin operations (background jobs, onboarding writes). Never reaches browser.

---

## 5. Demo Seed Data

Demo family: "The Reeds" — a family of 4 with realistic calendar data, food preferences, important dates, and conversation scenarios.

Located in: `supabase/seed/demo-family.sql`

Rules:
- Never uses real names or real data
- Covers all entities
- Includes edge cases (conflicts, recurring events, busy weeks, free evenings)
- `demo_mode = true` in families table
