"""
Google Calendar API provider.

This is the only file in the application that knows about Google's API.
It implements CalendarProvider using httpx for HTTP — no Google SDK required.

Read-only: only calendar.readonly scope is requested. Never writes, never
sends invites, never modifies events.

Token management:
- Receives decrypted access_token for API calls
- Detects 401 responses → raises TokenExpiredError so caller can refresh
- After refresh: caller (calendar routes) stores the new encrypted token
- Never stores tokens in memory beyond the request lifecycle
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.providers.calendar.base import CalendarEvent, CalendarProvider
from app.providers.calendar.normalizer import normalize_google_event

UTC = ZoneInfo("UTC")


class TokenExpiredError(Exception):
    """Raised when Google returns 401 — caller should refresh the access token."""
    pass


class GoogleCalendarProvider(CalendarProvider):
    """
    Google Calendar API v3 client.

    Constructor args are the OAuth credentials from settings — they stay
    server-side and are never exposed to the browser.
    """

    BASE_URL = "https://www.googleapis.com/calendar/v3"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def build_oauth_url(self, state: str) -> str:
        """
        Build the Google OAuth 2.0 authorization URL.

        Requests offline access so we receive a refresh token.
        Prompts consent on every auth so refresh_token is always returned.
        Only calendar.readonly scope is included — no write scope.
        """
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": self.SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def get_events(
        self,
        calendar_id: str,
        family_member_id: str,
        start: datetime,
        end: datetime,
        access_token: str = "",
    ) -> list[CalendarEvent]:
        """
        Fetch events from a Google calendar in the given time window.

        Raises TokenExpiredError on 401 so the caller can refresh and retry.
        Normalizes every item through normalize_google_event — skipping
        declined invites (returns None).
        """
        url = f"{self.BASE_URL}/calendars/{urllib.parse.quote(calendar_id)}/events"
        params = {
            "timeMin": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "timeMax": end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code == 401:
            raise TokenExpiredError("Google Calendar access token expired")

        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])

        events: list[CalendarEvent] = []
        for raw in items:
            # family_id is not available here — will be set by the route layer
            event = normalize_google_event(
                raw,
                calendar_id=calendar_id,
                family_id="",           # Populated by caller
                family_member_id=family_member_id,
            )
            if event is not None:
                events.append(event)

        return events

    async def get_calendars(self, access_token: str) -> list[dict]:
        """
        Return a list of calendar entries from the user's Google Calendar list.
        """
        url = f"{self.BASE_URL}/users/me/calendarList"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 401:
            raise TokenExpiredError("Google Calendar access token expired")

        response.raise_for_status()
        data = response.json()
        return data.get("items", [])

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """
        Exchange an OAuth authorization code for access + refresh tokens.

        Returns a dict with at minimum:
            {access_token, refresh_token, expires_in, token_type}
        """
        payload = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data=payload)

        response.raise_for_status()
        return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Use a stored refresh token to get a new access token.

        Returns a dict with at minimum:
            {access_token, expires_in, token_type}
        """
        payload = {
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data=payload)

        response.raise_for_status()
        return response.json()
