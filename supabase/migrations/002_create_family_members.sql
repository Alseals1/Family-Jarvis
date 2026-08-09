CREATE TABLE family_members (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id    UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  relationship TEXT NOT NULL,  -- 'adult_partner', 'child', 'extended'
  birthday     DATE,
  email        TEXT,
  active       BOOLEAN NOT NULL DEFAULT true,
  user_id      UUID REFERENCES auth.users(id),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_family_members_family ON family_members(family_id);
CREATE INDEX idx_family_members_user   ON family_members(user_id);
