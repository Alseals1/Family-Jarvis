CREATE TABLE calendar_events (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  calendar_id       UUID NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
  family_member_id  UUID NOT NULL REFERENCES family_members(id),
  external_id       TEXT,
  title             TEXT NOT NULL,
  -- description treated as untrusted data — never executed as instructions
  description       TEXT,
  start_time        TIMESTAMPTZ NOT NULL,
  end_time          TIMESTAMPTZ NOT NULL,
  all_day           BOOLEAN NOT NULL DEFAULT false,
  location          TEXT,
  recurrence_rule   TEXT,
  status            TEXT NOT NULL DEFAULT 'confirmed'
                      CHECK (status IN ('confirmed', 'tentative', 'cancelled')),
  source            TEXT NOT NULL CHECK (source IN ('google', 'apple', 'outlook', 'manual')),
  raw_data          JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Primary query pattern: get events for a family in a time window
CREATE INDEX idx_calendar_events_family_time
  ON calendar_events(family_id, start_time, end_time);

-- Secondary: per-member schedule
CREATE INDEX idx_calendar_events_member_time
  ON calendar_events(family_member_id, start_time);
