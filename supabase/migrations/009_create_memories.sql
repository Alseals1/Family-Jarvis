-- Explicit-only memories: user must ask JARVIS to remember something.
-- JARVIS always confirms aloud what was saved. Never silent.
CREATE TABLE memories (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id  UUID REFERENCES family_members(id),
  content           TEXT NOT NULL,
  category          TEXT,  -- 'preference', 'event', 'fact', 'relationship'
  confirmed_to_user BOOLEAN NOT NULL DEFAULT true,
  source            TEXT NOT NULL DEFAULT 'explicit'
                      CHECK (source = 'explicit'),  -- only explicit saves allowed
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_memories_family ON memories(family_id);
