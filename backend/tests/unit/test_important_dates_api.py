from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.api.routes.important_dates import _next_occurrence

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
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    m = MagicMock()
    m.table.return_value = chain
    return m


# ── Pure logic tests (no HTTP) ─────────────────────────────────────────────

def test_next_occurrence_future_date_this_year():
    today = date(2026, 8, 9)
    d = date(1985, 12, 25)  # Christmas — still upcoming this year
    assert _next_occurrence(d, today) == date(2026, 12, 25)


def test_next_occurrence_past_date_this_year_rolls_to_next():
    today = date(2026, 8, 9)
    d = date(1985, 3, 14)  # March — already passed
    assert _next_occurrence(d, today) == date(2027, 3, 14)


def test_next_occurrence_today_is_included():
    today = date(2026, 8, 9)
    d = date(2000, 8, 9)   # birthday today
    assert _next_occurrence(d, today) == date(2026, 8, 9)


# ── API tests ─────────────────────────────────────────────────────────────

def test_list_dates_filters_by_type():
    client = _app()
    rows = [
        {"id": "1", "family_id": FAMILY_A, "label": "Anniversary", "date_type": "anniversary",
         "date": "1990-06-15", "recurs_yearly": True},
    ]
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.important_dates.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/dates?date_type=anniversary",
                          headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    assert resp.json()[0]["date_type"] == "anniversary"


def test_upcoming_dates_within_window():
    today = date.today()
    in_10 = (today + timedelta(days=10)).replace(year=1990)
    rows = [
        {"id": "1", "family_id": FAMILY_A, "label": "Birthday", "date_type": "birthday",
         "date": in_10.isoformat(), "recurs_yearly": True},
    ]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.important_dates.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/dates/upcoming?days=30",
                          headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "next_occurrence" in data[0]


def test_upcoming_dates_excludes_outside_window():
    today = date.today()
    far_future = (today + timedelta(days=90)).replace(year=1990)
    rows = [
        {"id": "2", "family_id": FAMILY_A, "label": "Trip", "date_type": "trip",
         "date": far_future.isoformat(), "recurs_yearly": False},
    ]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.important_dates.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/dates/upcoming?days=30",
                          headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_upcoming_dates_sorted_by_next_occurrence():
    today = date.today()
    day5  = (today + timedelta(days=5)).replace(year=1990)
    day15 = (today + timedelta(days=15)).replace(year=1990)
    rows = [
        {"id": "b", "family_id": FAMILY_A, "label": "B", "date_type": "birthday",
         "date": day15.isoformat(), "recurs_yearly": True},
        {"id": "a", "family_id": FAMILY_A, "label": "A", "date_type": "anniversary",
         "date": day5.isoformat(), "recurs_yearly": True},
    ]
    client = _app()
    mock_admin = _mock_db(rows)
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=mock_admin), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_A), \
         patch("app.api.routes.important_dates.get_supabase_admin", return_value=mock_admin):
        resp = client.get("/api/family/dates/upcoming?days=30",
                          headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    results = resp.json()
    assert results[0]["label"] == "A"  # closer date first
    assert results[1]["label"] == "B"
