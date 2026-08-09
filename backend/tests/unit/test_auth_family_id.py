from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}

FAMILY_ID = "fam-111"
USER_ID = "user-123"


def _make_auth_result(user_id=USER_ID, email="u@test.com"):
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


def test_me_includes_family_id_when_member_exists():
    auth_result = _make_auth_result()
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = auth_result
    # Simulate family_members lookup returning a family
    mock_admin.table.return_value.select.return_value.eq.return_value \
        .eq.return_value.limit.return_value.execute.return_value \
        .data = [{"family_id": FAMILY_ID}]

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.db.queries.family.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer valid"})

    assert response.status_code == 200
    data = response.json()
    assert data["family_id"] == FAMILY_ID
    assert data["user_id"] == USER_ID


def test_me_returns_null_family_id_when_not_onboarded():
    auth_result = _make_auth_result()
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = auth_result
    # No family_members row
    mock_admin.table.return_value.select.return_value.eq.return_value \
        .eq.return_value.limit.return_value.execute.return_value \
        .data = []

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.db.queries.family.get_supabase_admin", return_value=mock_admin):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer valid"})

    assert response.status_code == 200
    assert response.json()["family_id"] is None


def test_family_id_not_injectable_from_request_body():
    """family_id from request body must not override the JWT-derived value."""
    auth_result = _make_auth_result()
    mock_admin = MagicMock()
    mock_admin.auth.get_user.return_value = auth_result
    mock_admin.table.return_value.select.return_value.eq.return_value \
        .eq.return_value.limit.return_value.execute.return_value \
        .data = [{"family_id": FAMILY_ID}]

    client = _app_client()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.db.queries.family.get_supabase_admin", return_value=mock_admin):
        # Attacker tries to inject a different family_id via query param
        response = client.get(
            "/api/auth/me?family_id=evil-family-id",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    assert response.json()["family_id"] == FAMILY_ID  # JWT value, not the param
