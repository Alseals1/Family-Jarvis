-- RLS for all Phase 2 tables
-- Pattern: users may only access data belonging to their own family
-- family_id is always determined from family_members.user_id = auth.uid()
-- OAuth token columns (access_token_enc, refresh_token_enc) are excluded
-- from SELECT policies — written only via service-role backend operations.

ALTER TABLE calendars        ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE important_dates  ENABLE ROW LEVEL SECURITY;
ALTER TABLE preferences      ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories         ENABLE ROW LEVEL SECURITY;
ALTER TABLE trips            ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationships    ENABLE ROW LEVEL SECURITY;
ALTER TABLE date_history     ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications    ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks      ENABLE ROW LEVEL SECURITY;

-- Helper: reused expression for family membership check
-- SELECT family_id FROM family_members WHERE user_id = auth.uid()

CREATE POLICY "family_read_calendars"
  ON calendars FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_calendar_events"
  ON calendar_events FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_important_dates"
  ON important_dates FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_preferences"
  ON preferences FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_food_preferences"
  ON food_preferences FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_memories"
  ON memories FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_trips"
  ON trips FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_relationships"
  ON relationships FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_date_history"
  ON date_history FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_notifications"
  ON notifications FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));

CREATE POLICY "family_read_agent_tasks"
  ON agent_tasks FOR SELECT
  USING (family_id IN (
    SELECT family_id FROM family_members WHERE user_id = auth.uid()
  ));
