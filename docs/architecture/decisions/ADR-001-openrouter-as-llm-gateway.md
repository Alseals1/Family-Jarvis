# ADR-001: Use OpenRouter as LLM Gateway

**Date:** 2026-08-09
**Status:** Accepted
**Deciders:** Orchestrator (per build specification)

---

## Context

The system requires LLM calls for conversation, recommendations, and summarization. The choice of provider has cost, reliability, and flexibility implications.

## Decision

Use OpenRouter as the sole LLM gateway.

The application backend calls `https://openrouter.ai/api/v1` exclusively. No agent or service calls any model provider directly (Anthropic, OpenAI, Google, etc.).

## Rationale

- Provider-agnostic: can switch models without rewriting application code
- Cost controls: per-model billing, model selection per agent
- Single integration point: one API key, one client
- Model experimentation: try different models by changing an env var
- Fallback: can route to different provider if one is down

## Consequences

- All model calls go through OpenRouter — adds ~50-100ms latency
- OpenRouter availability becomes a dependency
- Model versioning managed through env vars, not code

## Implementation

```python
OPENROUTER_API_KEY=<from env>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

OPENROUTER_MODEL_MANAGER=anthropic/claude-3.5-sonnet
OPENROUTER_MODEL_ORGANIZER=anthropic/claude-3-haiku
OPENROUTER_MODEL_CHEF=anthropic/claude-3-sonnet
OPENROUTER_MODEL_PLANNER=anthropic/claude-3.5-sonnet
OPENROUTER_MODEL_FAST=anthropic/claude-3-haiku
```

The LLMProvider interface abstracts all model-specific behavior.
