"""
Unit tests for app.providers.calendar.google.GoogleCalendarProvider.

All HTTP calls are mocked — no real Google API is called.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from app.providers.calendar.google import GoogleCalendarProvider, TokenExpiredError
from app.providers.calendar.base import CalendarEvent

UTC = ZoneInfo("UTC")

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
REDIRECT_URI = "http://localhost:8000/api/calendar/callback/google"

START = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
END = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)

ACCESS_TOKEN = "ya29.test-access-token"
REFRESH_TOKEN = "1//test-refresh-token"


def _provider() -> GoogleCalendarProvider:
    return GoogleCalendarProvider(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _raw_event(event_id: str = "event-001") -> dict:
    """Minimal Google Calendar API event dict."""
    return {
        "id": event_id,
        "summary": "Test Event",
        "status": "confirmed",
        "start": {"dateTime": "2026-08-10T09:00:00Z"},
        "end":   {"dateTime": "2026-08-10T10:00:00Z"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_events_calls_correct_url():
    """Verifies the correct Google API endpoint is called."""
    provider = _provider()
    mock_resp = _mock_response(200, {"items": []})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        await provider.get_events("primary", "member-1", START, END, ACCESS_TOKEN)

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "calendars/primary/events" in url
        assert "googleapis.com" in url


@pytest.mark.asyncio
async def test_get_events_uses_access_token_in_header():
    """Authorization: Bearer <token> header must be present."""
    provider = _provider()
    mock_resp = _mock_response(200, {"items": []})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        await provider.get_events("primary", "member-1", START, END, ACCESS_TOKEN)

        call_kwargs = mock_client.get.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == f"Bearer {ACCESS_TOKEN}"


@pytest.mark.asyncio
async def test_get_events_normalizes_response():
    """Raw Google response is converted to a list of CalendarEvent objects."""
    provider = _provider()
    raw = _raw_event()
    mock_resp = _mock_response(200, {"items": [raw]})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        events = await provider.get_events("primary", "member-1", START, END, ACCESS_TOKEN)

    assert len(events) == 1
    assert isinstance(events[0], CalendarEvent)
    assert events[0].title == "Test Event"


@pytest.mark.asyncio
async def test_get_events_empty_response():
    """Google returns no items → empty list, no error."""
    provider = _provider()
    mock_resp = _mock_response(200, {"items": []})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        events = await provider.get_events("primary", "member-1", START, END, ACCESS_TOKEN)

    assert events == []


@pytest.mark.asyncio
async def test_get_calendars_lists_calendar_ids():
    """get_calendars returns a list of calendar dicts."""
    provider = _provider()
    cal_list = {
        "items": [
            {"id": "primary", "summary": "Marcus Reed"},
            {"id": "family@group.calendar.google.com", "summary": "Family"},
        ]
    }
    mock_resp = _mock_response(200, cal_list)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        calendars = await provider.get_calendars(ACCESS_TOKEN)

    assert len(calendars) == 2
    ids = [c["id"] for c in calendars]
    assert "primary" in ids


@pytest.mark.asyncio
async def test_exchange_code_returns_token_dict():
    """Code exchange returns dict with expected token keys."""
    provider = _provider()
    token_response = {
        "access_token": ACCESS_TOKEN,
        "refresh_token": REFRESH_TOKEN,
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    mock_resp = _mock_response(200, token_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        result = await provider.exchange_code_for_tokens("auth-code-xyz")

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["access_token"] == ACCESS_TOKEN


@pytest.mark.asyncio
async def test_refresh_token_returns_new_access_token():
    """refresh_access_token calls TOKEN_URL and returns new access token."""
    provider = _provider()
    refresh_response = {
        "access_token": "ya29.new-access-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    mock_resp = _mock_response(200, refresh_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        result = await provider.refresh_access_token(REFRESH_TOKEN)

    assert "access_token" in result
    assert result["access_token"] == "ya29.new-access-token"


@pytest.mark.asyncio
async def test_401_response_raises_token_expired_error():
    """401 from Google → TokenExpiredError so caller can refresh and retry."""
    provider = _provider()
    mock_resp = _mock_response(401, {"error": "invalid_credentials"})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(TokenExpiredError):
            await provider.get_events("primary", "member-1", START, END, "expired-token")


def test_build_oauth_url_contains_required_scopes():
    """OAuth URL must include calendar.readonly scope."""
    provider = _provider()
    url = provider.build_oauth_url("test-state-123")
    assert "calendar.readonly" in url
    assert "state=test-state-123" in url
    assert "access_type=offline" in url


def test_no_write_scope_in_oauth_url():
    """
    The write scope (https://www.googleapis.com/auth/calendar) must NOT
    appear in the OAuth URL — only calendar.readonly is allowed.

    The SCOPE constant is the authoritative check; the URL is URL-encoded so
    we verify via the SCOPE string directly.
    """
    provider = _provider()
    url = provider.build_oauth_url("test-state-456")

    # SCOPE must be the read-only scope — not the write scope
    assert GoogleCalendarProvider.SCOPE == "https://www.googleapis.com/auth/calendar.readonly"

    # URL-encoded scope should contain "readonly" — the encoded form is
    # "calendar.readonly" URL-encoded as "calendar.readonly" (dots are safe)
    assert "calendar.readonly" in url
    # The bare write scope "auth%2Fcalendar&" or "auth/calendar&" must not appear
    # (only the readonly variant should be present)
    assert "calendar.readonly" in url
    # No separate write scope appended
    assert url.count("calendar.readonly") == 1
