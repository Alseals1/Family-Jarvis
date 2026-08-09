-- General key-value preferences (family-wide or per member)
CREATE TABLE preferences (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id  UUID REFERENCES family_members(id),  -- null = family-wide
  category          TEXT NOT NULL,  -- 'dining', 'activities', 'communication', 'scheduling'
  key               TEXT NOT NULL,
  value             JSONB NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (family_id, family_member_id, category, key)
);

-- Food preferences: favorites, dislikes, restrictions, allergies
CREATE TABLE food_preferences (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id  UUID REFERENCES family_members(id),  -- null = family-wide
  preference_type   TEXT NOT NULL
                      CHECK (preference_type IN ('favorite', 'dislike', 'restriction', 'allergy')),
  item              TEXT NOT NULL,
  notes             TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_food_prefs_family ON food_preferences(family_id);
