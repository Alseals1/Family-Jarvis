"""
Conversation context manager for Family JARVIS.

Maintains a sliding window of conversation history per session, keyed by
session_id. All state is in-memory — suitable for a single async process.
Persistent conversation history is a Phase 6 concern.
"""

from __future__ import annotations

from app.agents.contracts import ConversationTurn


class ConversationContextManager:
    MAX_TURNS: int = 10

    def __init__(self) -> None:
        self._sessions: dict[str, list[ConversationTurn]] = {}

    def get_or_create(self, session_id: str, family_id: str) -> list[ConversationTurn]:
        """Return current turns for session (empty list if new session)."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return list(self._sessions[session_id])

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Append turn; trim to MAX_TURNS (oldest dropped first)."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(turn)
        if len(self._sessions[session_id]) > self.MAX_TURNS:
            self._sessions[session_id] = self._sessions[session_id][-self.MAX_TURNS :]

    def clear(self, session_id: str) -> None:
        """Remove session from memory."""
        self._sessions.pop(session_id, None)

    def get_last_n(self, session_id: str, n: int) -> list[ConversationTurn]:
        """Return last N turns, or all if fewer than N exist."""
        turns = self._sessions.get(session_id, [])
        return list(turns[-n:]) if n > 0 else []

    def session_count(self) -> int:
        """Number of active sessions (for health/monitoring)."""
        return len(self._sessions)
