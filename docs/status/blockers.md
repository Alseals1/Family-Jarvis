# Family JARVIS — Blockers

**Updated:** 2026-08-09

---

## Active Blockers

### BLOCKER-001: User Architecture Approval
**Type:** Approval gate
**Blocking:** All implementation (Phase 1+)
**Resolution:** User reviews and approves architecture, data model, security model, and Phase 1 plan

### BLOCKER-002: UI Screenshot Gate
**Type:** Design gate
**Blocking:** All visual UI work (Phase 8)
**Resolution:** User provides a screenshot reference for visual language
**Note:** Frontend shell (Phase 1) can be built without visual design

### BLOCKER-003: Agent Stub Files Are Empty
**Type:** Implementation dependency
**Blocking:** Any invocation of specialist agents
**Resolution:** Orchestrator fills in agent definitions after architecture is approved
**Files affected:**
- `.claude/agents/product-architect.md`
- `.claude/agents/systems-architect.md`
- `.claude/agents/database-architect.md`
- `.claude/agents/backend-engineer.md`
- `.claude/agents/frontend-engineer.md`
- `.claude/agents/ui-ux-designer.md`
- `.claude/agents/ai-agent-architect.md`
- `.claude/agents/voice-engineer.md`
- `.claude/agents/integration-engineer.md`
- `.claude/agents/security-engineer.md`
- `.claude/agents/qa-engineer.md`
- `.claude/agents/devops-engineer.md`
- `.claude/agents/technical-writer.md`

---

## Resolved Blockers

_(None yet — project in planning phase)_
