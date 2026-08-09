import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}


def _make_supabase_result(user_id="user-123", email="test@example.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    result = MagicMock()
    result.user = user
    return result


def _app_client():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def test_get_me_returns_user_when_valid_token():
    result = _make_supabase_result()
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = result

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-123"
    assert data["email"] == "test@example.com"


def test_missing_authorization_header_returns_403():
    client = _app_client()
    response = client.get("/api/auth/me")
    # HTTPBearer returns 403 when the header is entirely absent
    assert response.status_code == 403


def test_invalid_token_raises_401():
    mock_admin = MagicMock()
    mock_admin.auth.get_user.side_effect = Exception("invalid JWT")

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_null_user_in_result_returns_401():
    mock_result = MagicMock()
    mock_result.user = None
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = mock_result

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer some-token"})

    assert response.status_code == 401


def test_family_id_not_in_response_until_phase_2():
    """family_id is resolved in Phase 2 — not present in /me response yet."""
    result = _make_supabase_result()
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = result

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert "family_id" not in response.json()
