"""
Unit tests for calendar API routes.

All DB and Google Calendar provider calls are mocked.
Verifies route logic and security invariants.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

UTC = ZoneInfo("UTC")

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
    "GOOGLE_CLIENT_ID": "test-client-id",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "CALENDAR_ENCRYPTION_KEY": "aa" * 32,  # 64 hex chars = valid key
}

FAMILY_ID = "fam-reeds"
MEMBER_ID = "mem-001"

CAL_ROW = {
    "id": "cal-001",
    "family_member_id": MEMBER_ID,
    "provider": "google",
    "external_id": "primary",
    "name": "Marcus Calendar",
    "last_synced_at": None,
}

EVENT_ROW = {
    "external_id": "evt-001",
    "calendar_id": "cal-001",
    "family_id": FAMILY_ID,
    "family_member_id": MEMBER_ID,
    "title": "Work standup",
    "description": None,
    "start_time": "2026-08-10T09:00:00+00:00",
    "end_time": "2026-08-10T09:30:00+00:00",
    "all_day": False,
    "location": None,
    "recurrence_rule": None,
    "status": "confirmed",
    "source": "google",
}


def _app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        get_settings()  # pre-populate cache with test values while env is patched
        from app.main import app
        return TestClient(app, raise_server_exceptions=False)


def _mock_auth(family_id: str = FAMILY_ID) -> MagicMock:
    mock = MagicMock()
    result = MagicMock()
    result.user = MagicMock()
    result.user.id = "user-marcus"
    result.user.email = "marcus@demo.jarvis"
    mock.auth.get_user.return_value = result
    return mock


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_status_returns_connected_calendars():
    """GET /status returns connected calendars with no token fields."""
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               new=AsyncMock(return_value=[CAL_ROW])):
        resp = client.get("/api/calendar/status", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["family_id"] == FAMILY_ID
    assert len(data["connected_calendars"]) == 1
    cal = data["connected_calendars"][0]
    assert "access_token_enc" not in cal
    assert "refresh_token_enc" not in cal


def test_connect_returns_oauth_url():
    """GET /connect/google returns a Google OAuth URL with calendar.readonly scope."""
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID):
        resp = client.get("/api/calendar/connect/google",
                          headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 200
    data = resp.json()
    assert "oauth_url" in data
    assert "accounts.google.com" in data["oauth_url"]
    assert "calendar.readonly" in data["oauth_url"]


def test_callback_missing_state_returns_400():
    """GET /callback/google with an unknown state → 400."""
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch.dict("app.api.routes.calendar._oauth_states", {}):
        resp = client.get(
            "/api/calendar/callback/google?code=test-code&state=bad-state",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 400


def test_callback_success_stores_encrypted_token():
    """After a valid OAuth callback, encrypted tokens (not plaintext) are stored."""
    client = _app()
    state = "valid-state-uuid"
    mock_provider = MagicMock()
    mock_provider.exchange_code_for_tokens = AsyncMock(return_value={
        "access_token": "plain-access-token",
        "refresh_token": "plain-refresh-token",
        "expires_in": 3600,
    })
    mock_provider.get_calendars = AsyncMock(return_value=[
        {"id": "primary", "summary": "Marcus Calendar"}
    ])
    stored_calls = []

    async def mock_store(**kwargs):
        stored_calls.append(kwargs)
        return "cal-001"

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.calendar._get_provider", return_value=mock_provider), \
         patch("app.api.routes.calendar.store_calendar_connection",
               side_effect=mock_store), \
         patch.dict("app.api.routes.calendar._oauth_states", {state: FAMILY_ID}):
        resp = client.get(
            f"/api/calendar/callback/google?code=auth-code&state={state}",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    assert len(stored_calls) == 1
    # Encrypted values must differ from plaintext
    assert stored_calls[0]["access_token_enc"] != "plain-access-token"
    assert stored_calls[0]["refresh_token_enc"] != "plain-refresh-token"
    # No plaintext field allowed in the store call
    assert "access_token" not in stored_calls[0]


def test_events_returns_correct_shape():
    """GET /events response has events, conflicts, and availability keys."""
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               new=AsyncMock(return_value=[CAL_ROW])), \
         patch("app.api.routes.calendar.get_events_in_range",
               new=AsyncMock(return_value=[EVENT_ROW])):
        resp = client.get(
            "/api/calendar/events?start=2026-08-09&end=2026-08-16",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "conflicts" in data
    assert "availability" in data


def test_events_no_calendar_connected_returns_empty():
    """No calendars connected → /events returns empty lists, not 500."""
    client = _app()
    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               new=AsyncMock(return_value=[])):
        resp = client.get(
            "/api/calendar/events?start=2026-08-09&end=2026-08-16",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []
    assert data["conflicts"] == []
    assert data["availability"] == []
    assert "message" in data and data["message"]


def test_events_conflict_detection_called():
    """detect_conflicts is invoked with the fetched CalendarEvent objects."""
    client = _app()
    passed_events = []

    def mock_detect(events):
        passed_events.extend(events)
        return []

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               new=AsyncMock(return_value=[CAL_ROW])), \
         patch("app.api.routes.calendar.get_events_in_range",
               new=AsyncMock(return_value=[EVENT_ROW])), \
         patch("app.api.routes.calendar.detect_conflicts", side_effect=mock_detect):
        resp = client.get(
            "/api/calendar/events?start=2026-08-09&end=2026-08-16",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    assert len(passed_events) == 1
    assert passed_events[0].title == "Work standup"


def test_sync_calls_google_provider():
    """POST /sync triggers GoogleCalendarProvider.get_events for connected calendars."""
    client = _app()
    mock_provider = MagicMock()
    mock_provider.get_events = AsyncMock(return_value=[])

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_supabase_admin", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               new=AsyncMock(return_value=[CAL_ROW])), \
         patch("app.api.routes.calendar.get_decrypted_tokens",
               new=AsyncMock(return_value=("enc-access", "enc-refresh",
                                           datetime.now(UTC)))), \
         patch("app.api.routes.calendar.decrypt_token", return_value="plain-token"), \
         patch("app.api.routes.calendar.upsert_calendar_events",
               new=AsyncMock(return_value=0)), \
         patch("app.api.routes.calendar.mark_calendar_synced", new=AsyncMock()), \
         patch("app.api.routes.calendar._get_provider", return_value=mock_provider), \
         patch.dict("app.api.routes.calendar._last_sync", {}):
        resp = client.post("/api/calendar/sync", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 200
    mock_provider.get_events.assert_called_once()


def test_sync_rate_limit_respected():
    """A second sync request within 5 minutes returns 429."""
    client = _app()
    recent = datetime.now(UTC) - timedelta(seconds=30)

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch.dict("app.api.routes.calendar._last_sync", {FAMILY_ID: recent}):
        resp = client.post("/api/calendar/sync", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 429


def test_events_family_id_from_jwt_not_query_param():
    """family_id passed as a query param is ignored — JWT family_id is always used."""
    client = _app()
    queried_family_ids = []

    async def mock_get_calendars(family_id, db):
        queried_family_ids.append(family_id)
        return []

    with patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth()), \
         patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID), \
         patch("app.api.routes.calendar.get_supabase", return_value=MagicMock()), \
         patch("app.api.routes.calendar.get_calendars_for_family",
               side_effect=mock_get_calendars):
        resp = client.get(
            "/api/calendar/events?start=2026-08-09&end=2026-08-16&family_id=evil-family",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    assert len(queried_family_ids) > 0
    assert all(fid == FAMILY_ID for fid in queried_family_ids)
    assert "evil-family" not in queried_family_ids
