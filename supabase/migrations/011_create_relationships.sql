-- Member-to-member relationships
CREATE TABLE relationships (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  member_a_id       UUID NOT NULL REFERENCES family_members(id),
  member_b_id       UUID NOT NULL REFERENCES family_members(id),
  relationship_type TEXT NOT NULL
                      CHECK (relationship_type IN ('partners', 'parent_child', 'siblings')),
  anniversary_date  DATE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (member_a_id <> member_b_id)
);

-- Past date-night history (used by Date Planner to avoid repetition)
CREATE TABLE date_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id       UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  relationship_id UUID REFERENCES relationships(id),
  date            DATE NOT NULL,
  activity        TEXT,
  restaurant      TEXT,
  notes           TEXT,
  rating          INT CHECK (rating BETWEEN 1 AND 5),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_relationships_family ON relationships(family_id);
CREATE INDEX idx_date_history_family   ON date_history(family_id, date);
