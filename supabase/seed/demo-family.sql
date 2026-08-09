-- Demo seed: "The Reeds" — synthetic family for demo/testing
-- Reference date: 2026-08-09
-- NEVER contains real family data. Safe to reset at any time.
-- family_id: 00000000-0000-0000-0000-000000000001

-- ── Families ───────────────────────────────────────────────────────────────
INSERT INTO families (id, name, timezone, demo_mode) VALUES
  ('00000000-0000-0000-0000-000000000001', 'The Reeds', 'America/Chicago', true)
ON CONFLICT (id) DO NOTHING;

-- ── Family Members ─────────────────────────────────────────────────────────
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
   'Zoe', 'child', '2018-11-30', NULL, true)
ON CONFLICT (id) DO NOTHING;

-- ── Important Dates ────────────────────────────────────────────────────────
-- Anniversary: 14 days from ref date (2026-08-23) → recurs yearly
INSERT INTO important_dates
  (family_id, family_member_id, label, date_type, date, recurs_yearly, lead_days) VALUES
  ('00000000-0000-0000-0000-000000000001', NULL,
   'Marcus & Priya Anniversary', 'anniversary', '2010-08-23', true, 14),

-- Eli's birthday: 10 days from ref (2026-08-19)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000003',
   'Eli''s Birthday', 'birthday', '2015-08-19', true, 14),

-- Zoe's birthday: ~3 months out (2026-11-30)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000004',
   'Zoe''s Birthday', 'birthday', '2018-11-30', true, 14),

-- Marcus birthday: already past this year (March)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'Marcus''s Birthday', 'birthday', '1985-03-14', true, 14),

-- Priya birthday: September (upcoming in ~6 weeks)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000002',
   'Priya''s Birthday', 'birthday', '1987-09-22', true, 14),

-- Upcoming trip: 2026-08-22 (13 days out)
  ('00000000-0000-0000-0000-000000000001', NULL,
   'Lake House Trip', 'trip', '2026-08-22', false, 7);

-- ── Relationships ──────────────────────────────────────────────────────────
INSERT INTO relationships
  (id, family_id, member_a_id, member_b_id, relationship_type, anniversary_date) VALUES
  ('00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000001',
   '00000000-0000-0000-0001-000000000002',
   'partners', '2010-08-23')
ON CONFLICT (id) DO NOTHING;

-- ── Date History ───────────────────────────────────────────────────────────
INSERT INTO date_history
  (family_id, relationship_id, date, activity, restaurant, rating) VALUES
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '2026-07-18', 'Dinner', 'Rosso Italian', 5),
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '2026-06-27', 'Movie + dinner', 'The Alley Bar + Grill', 4),
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '2026-05-31', 'Hiking + lunch', NULL, 5);

-- ── Food Preferences ───────────────────────────────────────────────────────
INSERT INTO food_preferences (family_id, family_member_id, preference_type, item, notes) VALUES
  -- Family-wide favorites
  ('00000000-0000-0000-0000-000000000001', NULL, 'favorite', 'Italian food', 'Especially pasta and pizza'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'favorite', 'Tacos', 'Any style'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'favorite', 'Sushi', 'Family-wide'),

  -- Priya: vegetarian
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000002',
   'restriction', 'meat', 'Priya is vegetarian'),

  -- Eli: peanut allergy (HARD CONSTRAINT — Chef Agent must always respect)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000003',
   'allergy', 'peanuts', 'Eli — severe peanut allergy'),

  -- Dislikes
  ('00000000-0000-0000-0000-000000000001', NULL, 'dislike', 'Brussels sprouts', 'Kids refuse'),
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'dislike', 'mushrooms', 'Marcus dislikes');

-- ── General Preferences ────────────────────────────────────────────────────
INSERT INTO preferences (family_id, family_member_id, category, key, value) VALUES
  ('00000000-0000-0000-0000-000000000001', NULL, 'dining', 'dinner_budget_usd',
   '{"min": 50, "max": 80}'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'dining', 'cooking_skill',
   '"medium"'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'dining', 'typical_prep_time_minutes',
   '45'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'activities', 'date_night_budget_usd',
   '{"min": 100, "max": 200}'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'activities', 'date_night_travel_minutes',
   '30'),
  ('00000000-0000-0000-0000-000000000001', NULL, 'activities', 'childcare_available',
   'true');

-- ── Memories ───────────────────────────────────────────────────────────────
INSERT INTO memories (family_id, family_member_id, content, category, confirmed_to_user, source) VALUES
  ('00000000-0000-0000-0000-000000000001', NULL,
   'We like the corner table at Rosso restaurant',
   'preference', true, 'explicit'),
  ('00000000-0000-0000-0000-000000000001', NULL,
   'The family went to Chicago for spring break 2026 and loved the architecture tour',
   'event', true, 'explicit'),
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000003',
   'Eli wants a Lego set for his birthday',
   'fact', true, 'explicit');

-- ── Trips ──────────────────────────────────────────────────────────────────
INSERT INTO trips (family_id, name, destination, departure_date, return_date,
                   travelers, status) VALUES
  ('00000000-0000-0000-0000-000000000001',
   'Lake House Weekend',
   'Lake Geneva, WI',
   '2026-08-22',
   '2026-08-24',
   ARRAY[
     '00000000-0000-0000-0001-000000000001'::uuid,
     '00000000-0000-0000-0001-000000000002'::uuid,
     '00000000-0000-0000-0001-000000000003'::uuid,
     '00000000-0000-0000-0001-000000000004'::uuid
   ],
   'planned');

-- ── Calendars (Phase 3) ─────────────────────────────────────────────────────
-- One calendar per family member. Adults use Google; children use manual.
-- Tokens are empty strings in seed (no real OAuth in demo mode).
INSERT INTO calendars
  (id, family_id, family_member_id, provider, external_id, name, sync_enabled)
VALUES
  ('00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'google', 'primary', 'Marcus Reed', true),
  ('00000000-0000-0000-0002-000000000002',
   '00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000002',
   'google', 'primary', 'Priya Reed', true),
  ('00000000-0000-0000-0002-000000000003',
   '00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000003',
   'manual', NULL, 'Eli Reed', true),
  ('00000000-0000-0000-0002-000000000004',
   '00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0001-000000000004',
   'manual', NULL, 'Zoe Reed', true)
ON CONFLICT (id) DO NOTHING;

-- ── Calendar Events (Phase 3 — week of 2026-08-09) ──────────────────────────
-- All times UTC. status='confirmed', source='manual' (no live sync in seed).
-- Friday is intentionally empty — free evening verified by absence.
-- Saturday: cross-member same-time scenario (different people, not a conflict).
-- Sunday: Marcus double-booked — same-person overlap (conflict scenario).
INSERT INTO calendar_events
  (family_id, calendar_id, family_member_id, external_id, title,
   start_time, end_time, all_day, status, source)
VALUES
  -- Monday Aug 10
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'seed-evt-mon-marcus', 'Work standup',
   '2026-08-10T09:00:00Z', '2026-08-10T09:30:00Z', false, 'confirmed', 'manual'),

  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000002',
   '00000000-0000-0000-0001-000000000002',
   'seed-evt-mon-priya', 'Client call',
   '2026-08-10T14:00:00Z', '2026-08-10T15:00:00Z', false, 'confirmed', 'manual'),

  -- Tuesday Aug 11
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000003',
   '00000000-0000-0000-0001-000000000003',
   'seed-evt-tue-eli', 'Soccer practice',
   '2026-08-11T16:00:00Z', '2026-08-11T17:30:00Z', false, 'confirmed', 'manual'),

  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000004',
   '00000000-0000-0000-0001-000000000004',
   'seed-evt-tue-zoe', 'Dance class',
   '2026-08-11T16:00:00Z', '2026-08-11T17:00:00Z', false, 'confirmed', 'manual'),

  -- Wednesday Aug 12
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'seed-evt-wed-marcus', 'Doctor appointment',
   '2026-08-12T10:00:00Z', '2026-08-12T11:00:00Z', false, 'confirmed', 'manual'),

  -- Thursday Aug 13
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000002',
   '00000000-0000-0000-0001-000000000002',
   'seed-evt-thu-priya', 'Work presentation',
   '2026-08-13T13:00:00Z', '2026-08-13T14:00:00Z', false, 'confirmed', 'manual'),

  -- Saturday Aug 15 — cross-member same time (scheduling awareness, not a conflict)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'seed-evt-sat-marcus', 'Soccer',
   '2026-08-15T10:00:00Z', '2026-08-15T11:00:00Z', false, 'confirmed', 'manual'),

  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000002',
   '00000000-0000-0000-0001-000000000002',
   'seed-evt-sat-priya', 'Dentist',
   '2026-08-15T10:00:00Z', '2026-08-15T11:30:00Z', false, 'confirmed', 'manual'),

  -- Sunday Aug 16 — Marcus double-booked (same-person conflict scenario)
  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'seed-evt-sun-marcus-a', 'Marcus double-booked A',
   '2026-08-16T14:00:00Z', '2026-08-16T15:00:00Z', false, 'confirmed', 'manual'),

  ('00000000-0000-0000-0000-000000000001',
   '00000000-0000-0000-0002-000000000001',
   '00000000-0000-0000-0001-000000000001',
   'seed-evt-sun-marcus-b', 'Marcus double-booked B',
   '2026-08-16T14:30:00Z', '2026-08-16T15:30:00Z', false, 'confirmed', 'manual')

ON CONFLICT DO NOTHING;
