CREATE TABLE agent_tasks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id    UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  task_type    TEXT NOT NULL,
  agent        TEXT NOT NULL,  -- 'manager', 'organizer', 'chef', 'date_planner'
  status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'done', 'failed')),
  inputs       JSONB,
  outputs      JSONB,
  error        TEXT,
  started_at   TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_tasks_family_status ON agent_tasks(family_id, status, created_at);
