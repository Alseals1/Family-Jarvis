-- Conversation sessions (schema only — used in Phase 4)
CREATE TABLE conversations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id        UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  user_id          UUID NOT NULL REFERENCES auth.users(id),
  session_id       TEXT NOT NULL UNIQUE,
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  turn_count       INT NOT NULL DEFAULT 0
);

CREATE TABLE conversation_turns (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  turn_number     INT NOT NULL,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT NOT NULL,
  agents_invoked  TEXT[],
  data_sources    TEXT[],
  llm_tokens      INT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_family    ON conversations(family_id);
CREATE INDEX idx_conversation_turns_conv ON conversation_turns(conversation_id, turn_number);

ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_read_own_conversations"
  ON conversations FOR SELECT
  USING (
    family_id IN (
      SELECT family_id FROM family_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "users_read_own_turns"
  ON conversation_turns FOR SELECT
  USING (
    conversation_id IN (
      SELECT id FROM conversations
      WHERE family_id IN (
        SELECT family_id FROM family_members WHERE user_id = auth.uid()
      )
    )
  );
