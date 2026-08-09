CREATE TABLE important_dates (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  family_member_id  UUID REFERENCES family_members(id),  -- null = whole family
  label             TEXT NOT NULL,
  date_type         TEXT NOT NULL
                      CHECK (date_type IN ('birthday', 'anniversary', 'trip', 'holiday', 'tradition', 'other')),
  date              DATE NOT NULL,
  recurs_yearly     BOOLEAN NOT NULL DEFAULT true,
  notes             TEXT,
  lead_days         INT NOT NULL DEFAULT 14,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_important_dates_family ON important_dates(family_id, date);
