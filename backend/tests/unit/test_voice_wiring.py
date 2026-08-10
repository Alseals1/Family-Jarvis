"""
Unit tests for voice router wiring — Phase 7 T4.

Verifies:
  - /api/listen and /api/speak are registered in the FastAPI app
  - Voice router prefix is /api
  - VoiceProvider is injectable via Depends()
  - Settings API key is used by the provider
  - ELEVENLABS_API_KEY never leaks into health, listen, or speak responses
  - Both voice routes require authentication

10 tests:
 1. test_listen_endpoint_registered_in_app
 2. test_speak_endpoint_registered_in_app
 3. test_voice_router_prefix_is_api
 4. test_voice_provider_dependency_injectable
 5. test_voice_provider_uses_settings_api_key
 6. test_elevenlabs_api_key_not_in_health_response
 7. test_elevenlabs_api_key_not_in_listen_response
 8. test_elevenlabs_api_key_not_in_speak_response
 9. test_listen_requires_auth
10. test_speak_requires_auth
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "secret-xi-key-DONOTLEAK",
    "ELEVENLABS_VOICE_ID": "voice-001",
}

FAMILY_ID = "fam-wiring-test"
USER_ID = "user-wiring-001"
AUTH_HEADER = {"Authorization": "Bearer test-token"}
FAKE_AUDIO = b"RIFF\x00\x00\x00\x00WAVEfmt "
FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        return app


def _make_client():
    app = _get_app()
    return TestClient(app, raise_server_exceptions=False)


def _mock_auth_admin():
    mock = MagicMock()
    result = MagicMock()
    result.user = MagicMock()
    result.user.id = USER_ID
    result.user.email = "test@demo.jarvis"
    mock.auth.get_user.return_value = result
    return mock


def _auth_patches():
    return [
        patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin()),
        patch("app.api.middleware.auth.get_family_id_for_user", return_value=FAMILY_ID),
    ]


def _mock_voice_provider():
    from app.providers.voice.base import TranscribeResult
    provider = MagicMock()
    provider.transcribe = AsyncMock(return_value=TranscribeResult(transcript="test"))
    provider.synthesize = AsyncMock(return_value=FAKE_MP3)
    return provider


def _settings_patch():
    s = MagicMock()
    s.elevenlabs_voice_id = "voice-001"
    s.elevenlabs_api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]
    return patch("app.api.routes.voice.get_settings", return_value=s)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_listen_endpoint_registered_in_app():
    """The /api/listen route is registered in the FastAPI app after T4 wiring."""
    app = _get_app()
    routes = [r.path for r in app.routes]
    assert "/api/listen" in routes


def test_speak_endpoint_registered_in_app():
    """The /api/speak route is registered in the FastAPI app after T4 wiring."""
    app = _get_app()
    routes = [r.path for r in app.routes]
    assert "/api/speak" in routes


def test_voice_router_prefix_is_api():
    """The voice router is registered with prefix /api (routes start with /api/)."""
    app = _get_app()
    listen_route = next((r for r in app.routes if getattr(r, "path", "") == "/api/listen"), None)
    speak_route = next((r for r in app.routes if getattr(r, "path", "") == "/api/speak"), None)
    assert listen_route is not None, "/api/listen not found in routes"
    assert speak_route is not None, "/api/speak not found in routes"


def test_voice_provider_dependency_injectable():
    """VoiceProvider can be injected via app.dependency_overrides."""
    app = _get_app()
    provider = _mock_voice_provider()

    from app.providers.voice import get_voice_provider
    app.dependency_overrides[get_voice_provider] = lambda: provider

    client = TestClient(app, raise_server_exceptions=False)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/listen",
            files={"audio": ("audio.wav", io.BytesIO(FAKE_AUDIO), "audio/wav")},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    # Clean up override
    del app.dependency_overrides[get_voice_provider]


def test_voice_provider_uses_settings_api_key():
    """get_voice_provider() reads ELEVENLABS_API_KEY from settings (not hardcoded)."""
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.voice import get_voice_provider
        from app.providers.voice.elevenlabs import ElevenLabsProvider

        provider = get_voice_provider()
        assert isinstance(provider, ElevenLabsProvider)
        # The provider must have the key set from settings
        assert provider._api_key == REQUIRED_ENV["ELEVENLABS_API_KEY"]


def test_elevenlabs_api_key_not_in_health_response():
    """ELEVENLABS_API_KEY never appears in /health response body or headers."""
    api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]

    with patch("app.db.supabase.get_supabase_admin", return_value=MagicMock()):
        client = _make_client()
        response = client.get("/health")

    body_str = response.text
    assert api_key not in body_str
    for header_val in response.headers.values():
        assert api_key not in header_val


def test_elevenlabs_api_key_not_in_listen_response():
    """ELEVENLABS_API_KEY never appears in /api/listen response body or headers."""
    api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]
    app = _get_app()
    provider = _mock_voice_provider()

    from app.providers.voice import get_voice_provider
    app.dependency_overrides[get_voice_provider] = lambda: provider
    client = TestClient(app, raise_server_exceptions=False)

    with _auth_patches()[0], _auth_patches()[1]:
        response = client.post(
            "/api/listen",
            files={"audio": ("audio.wav", io.BytesIO(FAKE_AUDIO), "audio/wav")},
            headers=AUTH_HEADER,
        )

    assert api_key not in response.text
    for header_val in response.headers.values():
        assert api_key not in header_val

    del app.dependency_overrides[get_voice_provider]


def test_elevenlabs_api_key_not_in_speak_response():
    """ELEVENLABS_API_KEY never appears in /api/speak response body or headers."""
    api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]
    app = _get_app()
    provider = _mock_voice_provider()

    from app.providers.voice import get_voice_provider
    app.dependency_overrides[get_voice_provider] = lambda: provider
    client = TestClient(app, raise_server_exceptions=False)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": "Hello world."},
            headers=AUTH_HEADER,
        )

    # API key must not appear in binary response either
    assert api_key.encode() not in response.content
    for header_val in response.headers.values():
        assert api_key not in header_val

    del app.dependency_overrides[get_voice_provider]


def test_listen_requires_auth():
    """POST /api/listen without auth header returns 401 or 403."""
    client = _make_client()
    response = client.post(
        "/api/listen",
        files={"audio": ("audio.wav", io.BytesIO(FAKE_AUDIO), "audio/wav")},
    )
    assert response.status_code in (401, 403)


def test_speak_requires_auth():
    """POST /api/speak without auth header returns 401 or 403."""
    client = _make_client()
    response = client.post(
        "/api/speak",
        json={"text": "Hello."},
    )
    assert response.status_code in (401, 403)
