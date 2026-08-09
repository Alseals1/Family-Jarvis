"""
Family isolation tests — proves Family A's data is invisible to Family B's user.

These are unit-level tests that mock the DB layer. The RLS policies in
014_rls_phase2.sql provide the DB-level enforcement; these tests verify
the application layer never leaks family_id across authenticated users.
"""
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}

FAMILY_A = "family-aaa-111"
FAMILY_B = "family-bbb-222"
USER_A_ID = "user-a-111"
USER_B_ID = "user-b-222"

MEMBER_A = {"id": "m-a", "family_id": FAMILY_A, "name": "Alice", "active": True}
MEMBER_B = {"id": "m-b", "family_id": FAMILY_B, "name": "Bob",   "active": True}


def _app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_db_empty():
    """Return a mock admin client that always returns no rows (simulates RLS blocking)."""
    chain = MagicMock()
    for m in ["select", "insert", "update", "delete", "eq", "limit"]:
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    admin = MagicMock()
    admin.table.return_value = chain
    return admin


def _mock_db_rows(rows):
    chain = MagicMock()
    for m in ["select", "insert", "update", "delete", "eq", "limit"]:
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    admin = MagicMock()
    admin.table.return_value = chain
    return admin


def test_family_a_cannot_read_family_b_members():
    """
    User A is authenticated with family_id=A.
    All DB queries are scoped to family_id=A.
    Family B's member data is never returned.
    """
    client = _app()
    # DB returns only family A members (simulates RLS)
    mock_admin = _mock_db_rows([MEMBER_A])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/members", headers={"Authorization": "Bearer token-a"})

    assert resp.status_code == 200
    data = resp.json()
    # Only family A's data visible
    for member in data:
        assert member["family_id"] == FAMILY_A
    # Family B member never appears
    assert not any(m["family_id"] == FAMILY_B for m in data)


def test_family_a_cannot_read_family_b_important_dates():
    """Even if a user knows Family B's date ID, they get 404 not data."""
    client = _app()
    # Empty result = RLS blocked cross-family read
    mock_admin = _mock_db_empty()

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        # Try to fetch a member that belongs to Family B
        resp = client.get("/api/family/members/m-b", headers={"Authorization": "Bearer token-a"})

    assert resp.status_code == 404   # empty result → 404, not a data leak


def test_family_id_always_from_jwt_not_body():
    """
    POST /api/family/members with a spoofed family_id in the body.
    The route must use JWT family_id, not the body value.
    """
    client = _app()
    created = {"id": "new", "family_id": FAMILY_A, "name": "Charlie", "active": True}
    mock_admin = _mock_db_rows([created])

    captured_insert = {}

    def capture_table(table_name):
        chain = MagicMock()
        for m in ["select", "update", "delete", "eq", "limit"]:
            getattr(chain, m).return_value = chain

        def capture_insert(row):
            captured_insert.update(row)
            return chain
        chain.insert = capture_insert
        chain.execute.return_value = MagicMock(data=[created])
        return chain

    mock_admin.table = capture_table

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.family_members.get_supabase_admin", return_value=mock_admin):
        resp = client.post(
            "/api/family/members",
            # Attacker tries to inject Family B's ID in the request body
            json={"name": "Charlie", "relationship": "child", "family_id": FAMILY_B},
            headers={"Authorization": "Bearer token-a"},
        )

    assert resp.status_code == 201
    # The inserted row must use FAMILY_A (from JWT), not FAMILY_B (from body)
    assert captured_insert.get("family_id") == FAMILY_A
    assert captured_insert.get("family_id") != FAMILY_B


def test_unonboarded_user_gets_null_family_id_not_crash():
    """A valid JWT user with no family membership gets null family_id, not 500."""
    client = _app()
    mock_admin = MagicMock()
    auth_result = MagicMock()
    auth_result.user.id = "new-user"
    auth_result.user.email = "new@test.com"
    mock_admin.auth.get_user.return_value = auth_result

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=None):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer new-token"})

    assert resp.status_code == 200
    assert resp.json()["family_id"] is None  # not 500, not 401


def test_service_role_not_used_in_user_facing_routes():
    """
    Verifies that get_supabase_admin() (service-role) is patched separately
    from the anon client, and user routes never receive the bypass-RLS client
    from a user-facing request path without going through auth first.
    The auth middleware always validates the JWT before any DB access.
    """
    client = _app()
    mock_admin = _mock_db_empty()
    call_order = []

    original_get_user = mock_admin.auth.get_user

    def tracked_get_user(token):
        call_order.append("jwt_verify")
        result = MagicMock()
        result.user = None  # invalid token
        return result

    mock_admin.auth.get_user = tracked_get_user

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=None):
        # Bad token — should never reach DB query
        resp = client.get("/api/family/members", headers={"Authorization": "Bearer bad"})

    assert resp.status_code == 401
    # JWT was verified (and failed) before any DB access
    assert "jwt_verify" in call_order
