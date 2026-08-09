"""
Tests for ConversationContextManager — sliding window, session isolation, bounds.
"""

import pytest
from app.agents.context import ConversationContextManager
from app.agents.contracts import ConversationTurn

TS = "2026-08-09T12:00:00Z"


def _turn(turn_id: int, role: str = "user", content: str = "hi") -> ConversationTurn:
    return ConversationTurn(turn_id=turn_id, role=role, content=content, timestamp=TS)


def test_new_session_returns_empty_list():
    mgr = ConversationContextManager()
    turns = mgr.get_or_create("sess-001", "fam-001")
    assert turns == []


def test_add_turn_appends_to_session():
    mgr = ConversationContextManager()
    mgr.get_or_create("sess-001", "fam-001")
    mgr.add_turn("sess-001", _turn(1, "user", "What's up?"))
    mgr.add_turn("sess-001", _turn(2, "assistant", "Not much."))
    turns = mgr.get_or_create("sess-001", "fam-001")
    assert len(turns) == 2
    assert turns[0].content == "What's up?"
    assert turns[1].role == "assistant"


def test_sliding_window_drops_oldest_turn():
    mgr = ConversationContextManager()
    for i in range(12):
        mgr.add_turn("sess-001", _turn(i, content=f"msg {i}"))
    turns = mgr.get_or_create("sess-001", "fam-001")
    assert len(turns) == ConversationContextManager.MAX_TURNS
    # oldest turns (0,1) should be gone
    assert turns[0].content == "msg 2"
    assert turns[-1].content == "msg 11"


def test_window_never_exceeds_max_turns():
    mgr = ConversationContextManager()
    for i in range(50):
        mgr.add_turn("sess-abc", _turn(i))
    turns = mgr.get_or_create("sess-abc", "fam-001")
    assert len(turns) <= ConversationContextManager.MAX_TURNS


def test_two_sessions_isolated_from_each_other():
    mgr = ConversationContextManager()
    mgr.add_turn("sess-A", _turn(1, content="session A message"))
    mgr.add_turn("sess-B", _turn(1, content="session B message"))
    a_turns = mgr.get_or_create("sess-A", "fam-001")
    b_turns = mgr.get_or_create("sess-B", "fam-002")
    assert a_turns[0].content == "session A message"
    assert b_turns[0].content == "session B message"
    assert len(a_turns) == 1
    assert len(b_turns) == 1


def test_clear_removes_session():
    mgr = ConversationContextManager()
    mgr.add_turn("sess-001", _turn(1))
    mgr.clear("sess-001")
    turns = mgr.get_or_create("sess-001", "fam-001")
    assert turns == []


def test_get_last_n_respects_bounds():
    mgr = ConversationContextManager()
    for i in range(7):
        mgr.add_turn("sess-001", _turn(i, content=f"msg {i}"))
    last3 = mgr.get_last_n("sess-001", 3)
    assert len(last3) == 3
    assert last3[-1].content == "msg 6"

    last_all = mgr.get_last_n("sess-001", 20)
    assert len(last_all) == 7

    last_zero = mgr.get_last_n("sess-001", 0)
    assert last_zero == []


def test_session_count_tracks_active_sessions():
    mgr = ConversationContextManager()
    assert mgr.session_count() == 0
    mgr.add_turn("sess-001", _turn(1))
    assert mgr.session_count() == 1
    mgr.add_turn("sess-002", _turn(1))
    assert mgr.session_count() == 2
    mgr.clear("sess-001")
    assert mgr.session_count() == 1
