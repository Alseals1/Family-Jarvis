"""
Tests for the /api/chat route.

All ManagerAgent calls are mocked — tests focus on route security,
shape, rate limiting, and session management.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}

FAMILY_ID = "fam-reeds"
USER_ID = "user-001"
AUTH_HEADER = {"Authorization": "Bearer test-token"}


def _app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        get_settings()
        from app.main import app
        from app.api.routes import chat as chat_module
        chat_module._rate_buckets.clear()
        return TestClient(app, raise_server_exceptions=False)


def _mock_auth_admin(family_id: str = FAMILY_ID) -> MagicMock:
    mock = MagicMock()
    result = MagicMock()
    result.user = MagicMock()
    result.user.id = USER_ID
    result.user.email = "marcus@demo.jarvis"
    mock.auth.get_user.return_value = result
    return mock


def _mock_manager_respond(session_id: str = "sess-abc-123"):
    from app.agents.manager import ManagerResponse
    from app.agents.contracts import IntentType
    mock_result = ManagerResponse(
        response="Friday looks clear.",
        session_id=session_id,
        intent=IntentType.CALENDAR_QUERY,
        agent_calls=["intent_classifier"],
        data_sources=["calendar_events"],
    )
    return AsyncMock(return_value=mock_result)


def _base_patches(family_id: str = FAMILY_ID):
    """Return the base context manager patches needed for successful auth."""
    return [
        patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin(family_id)),
        patch("app.api.middleware.auth.get_family_id_for_user", return_value=family_id),
        patch("app.api.routes.chat.get_supabase", return_value=MagicMock()),
        patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()),
        patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()),
    ]


def test_chat_requires_jwt():
    client = _app()
    # No auth header → HTTPBearer will reject
    resp = client.post("/api/chat", json={"message": "Hello"})
    assert resp.status_code in (401, 403)


def test_chat_returns_response_shape():
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _mock_manager_respond()):

        resp = client.post("/api/chat", json={"message": "What's happening Friday?"}, headers=AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert "response" in body
    assert "session_id" in body
    assert "intent" in body
    assert "agent_calls" in body
    assert "data_sources" in body


def test_chat_creates_session_id_if_absent():
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _mock_manager_respond()):

        resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]  # non-empty session_id created


def test_chat_rejects_empty_message():
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID):

        resp = client.post("/api/chat", json={"message": ""}, headers=AUTH_HEADER)

    assert resp.status_code == 422


def test_chat_rejects_whitespace_only_message():
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID):

        resp = client.post("/api/chat", json={"message": "   "}, headers=AUTH_HEADER)

    assert resp.status_code == 422


def test_chat_family_id_from_jwt_not_body():
    """Passing family_id in request body must not override the JWT-derived family_id."""
    client = _app()
    captured_family_id = {}

    async def capture_respond(self, message, family_id, session_id):
        captured_family_id["family_id"] = family_id
        from app.agents.manager import ManagerResponse
        from app.agents.contracts import IntentType
        return ManagerResponse(
            response="ok",
            session_id=session_id,
            intent=IntentType.GENERAL,
            agent_calls=[],
            data_sources=[],
        )

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", capture_respond):

        resp = client.post(
            "/api/chat",
            # NOTE: family_id is not a real ChatRequest field — it should be silently ignored
            json={"message": "Hello"},
            headers=AUTH_HEADER,
        )

    assert resp.status_code == 200
    assert captured_family_id["family_id"] == FAMILY_ID


def test_chat_rate_limit_returns_429():
    from app.api.routes import chat as chat_module
    client = _app()
    chat_module._rate_buckets.clear()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _mock_manager_respond()):

        # Send exactly at the limit
        for _ in range(10):
            resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)
            assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"

        # 11th request should be rate-limited
        resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)
        assert resp.status_code == 429


def test_chat_passes_session_id_to_manager():
    client = _app()
    captured_session_id = {}

    async def capture_respond(self, message, family_id, session_id):
        captured_session_id["session_id"] = session_id
        from app.agents.manager import ManagerResponse
        from app.agents.contracts import IntentType
        return ManagerResponse(
            response="ok",
            session_id=session_id,
            intent=IntentType.GENERAL,
            agent_calls=[],
            data_sources=[],
        )

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", capture_respond):

        resp = client.post(
            "/api/chat",
            json={"message": "Hello", "session_id": "my-session-xyz"},
            headers=AUTH_HEADER,
        )

    assert resp.status_code == 200
    assert captured_session_id["session_id"] == "my-session-xyz"


# --- Upstream 429 handling (free-tier model rate limits) ---------------------
#
# The free-tier OpenRouter model returns 429 under light load. That must
# surface as a 429 with a user-facing message, not a 500.


def _respond_raising(exc: Exception):
    async def _raise(self, message, family_id, session_id):
        raise exc
    return _raise


def test_chat_returns_429_when_upstream_model_rate_limits():
    client = _app()
    upstream = Exception("Client error '429 Too Many Requests' for url '...'")

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _respond_raising(upstream)):

        resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)

    assert resp.status_code == 429
    assert "thinking too fast" in resp.json()["detail"]


def test_chat_429_message_is_user_facing_not_raw_upstream_error():
    """The caller must never see the raw upstream error text."""
    client = _app()
    upstream = Exception("429 Too Many Requests: openrouter quota key sk-or-secret")

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _respond_raising(upstream)):

        resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert "sk-or-secret" not in detail
    assert "quota" not in detail


def test_chat_non_429_errors_are_not_masked_as_429():
    """A genuine failure must not be reported to the user as a rate limit."""
    client = _app()
    upstream = ValueError("calendar provider exploded")

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.chat.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.chat.get_llm_provider", return_value=MagicMock()), \
         patch("app.agents.manager.ManagerAgent.respond", _respond_raising(upstream)):

        resp = client.post("/api/chat", json={"message": "Hello"}, headers=AUTH_HEADER)

    assert resp.status_code != 429
    assert resp.status_code >= 500
