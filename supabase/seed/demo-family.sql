-- Demo seed: "The Reeds" — synthetic family for demo/testing
-- NEVER contains real family data
-- Requires demo_mode = true; safe to reset at any time

INSERT INTO families (id, name, timezone, demo_mode) VALUES
  ('00000000-0000-0000-0000-000000000001', 'The Reeds', 'America/Chicago', true);

INSERT INTO family_members (id, family_id, name, relationship, birthday, email, active) VALUES
  ('00000000-0000-0000-0001-000000000001',
   '00000000-0000-0000-0000-000000000001',
   'Marcus', 'adult_partner', '1985-03-14', 'marcus.reed@demo.jarvis', true),

  ('00000000-0000-0000-0001-000000000002',
   '00000000-0000-0000-0000-000000000001',
   'Priya', 'adult_partner', '1987-09-22', 'priya.reed@demo.jarvis', true),

  ('00000000-0000-0000-0001-000000000003',
   '00000000-0000-0000-0000-000000000001',
   'Eli', 'child', '2015-06-05', NULL, true),

  ('00000000-0000-0000-0001-000000000004',
   '00000000-0000-0000-0000-000000000001',
   'Zoe', 'child', '2018-11-30', NULL, true);
