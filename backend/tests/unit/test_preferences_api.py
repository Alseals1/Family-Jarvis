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


def _app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_db(rows):
    chain = MagicMock()
    for m in ["select", "insert", "update", "delete", "eq"]:
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    admin = MagicMock()
    admin.table.return_value = chain
    return admin


def test_list_food_prefs_returns_family_data():
    rows = [
        {"id": "1", "family_id": FAMILY_A, "preference_type": "allergy", "item": "peanuts"},
        {"id": "2", "family_id": FAMILY_A, "preference_type": "favorite", "item": "Italian"},
    ]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.preferences.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/food", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_allergy_type_is_retrievable():
    rows = [{"id": "1", "family_id": FAMILY_A, "preference_type": "allergy", "item": "peanuts", "family_member_id": "eli-id"}]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.preferences.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/food?preference_type=allergy",
                          headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["preference_type"] == "allergy"
    assert data[0]["item"] == "peanuts"


def test_family_wide_preference_null_member_id():
    rows = [{"id": "1", "family_id": FAMILY_A, "category": "dining",
             "key": "budget", "value": {"min": 50, "max": 80}, "family_member_id": None}]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.preferences.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/preferences", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["family_member_id"] is None  # family-wide


def test_create_food_pref_injects_family_id():
    created = {"id": "new-1", "family_id": FAMILY_A, "preference_type": "favorite", "item": "tacos"}
    client = _app()
    mock_admin = _mock_db([created])
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.preferences.get_supabase_admin", return_value=mock_admin):
        resp = client.post("/api/family/food",
                           json={"preference_type": "favorite", "item": "tacos"},
                           headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 201


def test_no_family_id_returns_403():
    client = _app()
    mock_admin = MagicMock()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=None):
        resp = client.get("/api/family/food", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 403
