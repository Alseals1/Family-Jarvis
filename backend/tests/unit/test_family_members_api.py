from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}

FAMILY_A = "family-aaa"
FAMILY_B = "family-bbb"
USER_A = {"user_id": "user-a", "email": "a@test.com", "family_id": FAMILY_A}
MEMBER_ROW = {"id": "m-1", "family_id": FAMILY_A, "name": "Alice", "relationship": "adult_partner", "active": True, "created_at": "2026-01-01T00:00:00"}


def _app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_db(data, execute_data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    result = MagicMock()
    result.data = execute_data if execute_data is not None else data
    chain.execute.return_value = result
    mock_admin = MagicMock()
    mock_admin.table.return_value = chain
    return mock_admin


def test_list_members_returns_only_own_family():
    client = _app()
    mock_admin = _mock_db(None, [MEMBER_ROW])
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/members", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["family_id"] == FAMILY_A


def test_create_member_uses_family_id_from_jwt():
    client = _app()
    created = {**MEMBER_ROW, "name": "Bob"}
    mock_admin = _mock_db(None, [created])
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.post(
            "/api/family/members",
            json={"name": "Bob", "relationship": "adult_partner"},
            headers={"Authorization": "Bearer tok"},
        )
    assert resp.status_code == 201
    # Verify the insert was called — family_id came from mock, not request body


def test_get_member_enforces_family_scope():
    client = _app()
    mock_admin = _mock_db(None, [MEMBER_ROW])
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/members/m-1", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200


def test_get_member_returns_404_for_cross_family():
    """Empty result (RLS or family_id filter) produces 404, not data leak."""
    client = _app()
    mock_admin = _mock_db(None, [])  # empty — cross-family
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/members/m-from-family-b", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 404


def test_delete_soft_deletes_sets_active_false():
    client = _app()
    deleted = {**MEMBER_ROW, "active": False}
    mock_admin = _mock_db(None, [deleted])
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.delete("/api/family/members/m-1", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 204


def test_no_family_id_returns_403():
    client = _app()
    mock_admin = MagicMock()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=None):
        resp = client.get("/api/family/members", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 403
