CREATE TABLE notifications (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id    UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  type         TEXT NOT NULL
                 CHECK (type IN ('birthday', 'anniversary', 'trip', 'conflict',
                                 'briefing', 'free_evening', 'dinner_suggestion')),
  content      TEXT NOT NULL,
  trigger_date DATE NOT NULL,
  delivered    BOOLEAN NOT NULL DEFAULT false,
  delivered_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_family_date ON notifications(family_id, trigger_date, delivered);
