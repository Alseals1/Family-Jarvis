CREATE TABLE calendars (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id  UUID NOT NULL REFERENCES family_members(id) ON DELETE CASCADE,
  provider          TEXT NOT NULL CHECK (provider IN ('google', 'apple', 'outlook', 'manual')),
  external_id       TEXT,
  name              TEXT NOT NULL,
  color             TEXT,
  sync_enabled      BOOLEAN NOT NULL DEFAULT true,
  last_synced_at    TIMESTAMPTZ,
  -- OAuth tokens — stored encrypted, never returned to frontend
  access_token_enc  TEXT,
  refresh_token_enc TEXT,
  token_expiry      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_calendars_family  ON calendars(family_id);
CREATE INDEX idx_calendars_member  ON calendars(family_member_id);
