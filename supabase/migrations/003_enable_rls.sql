-- Enable RLS on all family-scoped tables
ALTER TABLE families        ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_members  ENABLE ROW LEVEL SECURITY;

-- families: a user can see their own family (the one they belong to as a member)
CREATE POLICY "users_read_own_family"
  ON families FOR SELECT
  USING (
    id IN (
      SELECT family_id FROM family_members
      WHERE user_id = auth.uid()
    )
  );

-- family_members: a user can read all members of their own family
CREATE POLICY "users_read_own_family_members"
  ON family_members FOR SELECT
  USING (
    family_id IN (
      SELECT family_id FROM family_members
      WHERE user_id = auth.uid()
    )
  );

-- family_members: a user can update/insert their own member record
CREATE POLICY "users_write_own_member_record"
  ON family_members FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
