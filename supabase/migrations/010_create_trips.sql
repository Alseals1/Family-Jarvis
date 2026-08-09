CREATE TABLE trips (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id       UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  destination     TEXT,
  departure_date  DATE,
  return_date     DATE,
  travelers       UUID[],   -- array of family_member IDs
  notes           TEXT,
  status          TEXT NOT NULL DEFAULT 'planned'
                    CHECK (status IN ('planned', 'active', 'completed', 'cancelled')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trips_family ON trips(family_id, departure_date);
