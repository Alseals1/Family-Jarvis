"""
Unit tests for POST /api/speak (TTS route) — Phase 7.

All ElevenLabs HTTP calls are mocked via FastAPI dependency_overrides.
No real network calls.

12 tests:
 1. test_speak_returns_200_with_valid_jwt_and_text
 2. test_speak_returns_401_without_jwt
 3. test_speak_returns_422_when_no_text
 4. test_speak_returns_audio_mpeg_content_type
 5. test_speak_returns_bytes_in_response_body
 6. test_speak_passes_text_to_voice_provider
 7. test_speak_uses_voice_id_from_env_not_request
 8. test_speak_strips_null_bytes_from_text
 9. test_speak_truncates_text_at_5000_chars
10. test_speak_empty_text_returns_422
11. test_speak_voice_provider_error_returns_502
12. test_speak_api_key_never_in_response_headers
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
    "ELEVENLABS_API_KEY": "test-xi-key-SECRET",
    "ELEVENLABS_VOICE_ID": "voice-env-001",
}

FAMILY_ID = "fam-speak-test"
USER_ID = "user-speak-001"
AUTH_HEADER = {"Authorization": "Bearer test-token"}
FAKE_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 200
SAMPLE_TEXT = "Friday looks clear until 6 PM. You have one meeting at 10."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        # Register voice router if not already registered (T4 wires it globally).
        voice_routes = [r.path for r in app.routes]
        if "/api/speak" not in voice_routes:
            from app.api.routes.voice import router as voice_router
            app.include_router(voice_router)
        return app


def _mock_auth_admin(family_id=FAMILY_ID):
    mock = MagicMock()
    result = MagicMock()
    result.user = MagicMock()
    result.user.id = USER_ID
    result.user.email = "test@demo.jarvis"
    mock.auth.get_user.return_value = result
    return mock


def _auth_patches(family_id=FAMILY_ID):
    return [
        patch("app.api.middleware.auth.get_supabase_admin", return_value=_mock_auth_admin(family_id)),
        patch("app.api.middleware.auth.get_family_id_for_user", return_value=family_id),
    ]


def _mock_settings(voice_id: str = "voice-env-001"):
    """Build a mock settings object for patching the voice route."""
    s = MagicMock()
    s.elevenlabs_voice_id = voice_id
    s.elevenlabs_api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]
    s.elevenlabs_tts_model = "eleven_multilingual_v2"
    s.elevenlabs_stt_model = "scribe_v1"
    return s


def _settings_patch(voice_id: str = "voice-env-001"):
    """Patch get_settings in the voice route module."""
    return patch(
        "app.api.routes.voice.get_settings",
        return_value=_mock_settings(voice_id),
    )


def _mock_voice_provider(audio_bytes: bytes = FAKE_MP3_BYTES):
    """Return a mock VoiceProvider whose synthesize() returns fixed MP3 bytes."""
    from app.providers.voice.base import TranscribeResult
    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=audio_bytes)
    provider.transcribe = AsyncMock(return_value=TranscribeResult(transcript="ok"))
    return provider


def _mock_voice_provider_error():
    """Return a mock VoiceProvider whose synthesize() raises VoiceProviderError."""
    from app.providers.voice.base import VoiceProviderError
    provider = MagicMock()
    provider.synthesize = AsyncMock(side_effect=VoiceProviderError("TTS error"))
    return provider


def _client_with_voice_override(voice_provider, extra_env: dict | None = None):
    """Build TestClient with the voice provider dependency overridden."""
    env = {**REQUIRED_ENV, **(extra_env or {})}
    with patch.dict("os.environ", env, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        voice_routes = [r.path for r in app.routes]
        if "/api/speak" not in voice_routes:
            from app.api.routes.voice import router as voice_router
            app.include_router(voice_router)
        from app.providers.voice import get_voice_provider
        app.dependency_overrides[get_voice_provider] = lambda: voice_provider
        client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_speak_returns_200_with_valid_jwt_and_text():
    """POST /api/speak with valid JWT and text returns 200."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200


def test_speak_returns_401_without_jwt():
    """POST /api/speak without JWT returns 401/403."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    response = client.post(
        "/api/speak",
        json={"text": SAMPLE_TEXT},
    )

    assert response.status_code in (401, 403)


def test_speak_returns_422_when_no_text():
    """POST /api/speak with missing 'text' field returns 422."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 422


def test_speak_returns_audio_mpeg_content_type():
    """POST /api/speak returns Content-Type: audio/mpeg."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"


def test_speak_returns_bytes_in_response_body():
    """POST /api/speak returns binary audio bytes in response body."""
    provider = _mock_voice_provider(audio_bytes=FAKE_MP3_BYTES)
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    assert response.content == FAKE_MP3_BYTES


def test_speak_passes_text_to_voice_provider():
    """POST /api/speak passes the sanitized text to voice_provider.synthesize()."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    call_args = provider.synthesize.call_args
    assert call_args.args[0] == SAMPLE_TEXT


def test_speak_uses_voice_id_from_env_not_request():
    """POST /api/speak uses ELEVENLABS_VOICE_ID from env, not from request body."""
    provider = _mock_voice_provider()
    env_voice_id = "voice-env-001"
    client = _client_with_voice_override(provider, extra_env={"ELEVENLABS_VOICE_ID": env_voice_id})

    with _auth_patches()[0], _auth_patches()[1], _settings_patch(voice_id=env_voice_id):
        client.post(
            "/api/speak",
            # Request body has no voice_id — it must come from env only
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    call_args = provider.synthesize.call_args
    # Second argument to synthesize() is voice_id
    assert call_args.args[1] == env_voice_id


def test_speak_strips_null_bytes_from_text():
    """POST /api/speak strips null bytes from text before calling provider."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)
    text_with_nulls = "Hello\x00 world\x00."

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        client.post(
            "/api/speak",
            json={"text": text_with_nulls},
            headers=AUTH_HEADER,
        )

    call_args = provider.synthesize.call_args
    passed_text = call_args.args[0]
    assert "\x00" not in passed_text
    assert "Hello" in passed_text
    assert "world" in passed_text


def test_speak_truncates_text_at_5000_chars():
    """POST /api/speak truncates text to 5000 chars before calling provider."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)
    long_text = "A" * 10_000

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        client.post(
            "/api/speak",
            json={"text": long_text},
            headers=AUTH_HEADER,
        )

    call_args = provider.synthesize.call_args
    passed_text = call_args.args[0]
    assert len(passed_text) == 5000


def test_speak_empty_text_returns_422():
    """POST /api/speak with empty string returns 422 (fails sanitization validator)."""
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": ""},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 422


def test_speak_voice_provider_error_returns_502():
    """POST /api/speak returns 502 when ElevenLabs TTS returns an error."""
    provider = _mock_voice_provider_error()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 502


def test_speak_api_key_never_in_response_headers():
    """POST /api/speak never returns ELEVENLABS_API_KEY in response headers."""
    api_key = REQUIRED_ENV["ELEVENLABS_API_KEY"]
    provider = _mock_voice_provider()
    client = _client_with_voice_override(provider)

    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        response = client.post(
            "/api/speak",
            json={"text": SAMPLE_TEXT},
            headers=AUTH_HEADER,
        )

    # Key must not appear in any response header value
    for header_name, header_value in response.headers.items():
        assert api_key not in header_value, (
            f"API key found in response header '{header_name}'"
        )


# ---------------------------------------------------------------------------
# Upstream status mapping
#
# Every provider failure used to collapse into "502 temporarily unavailable".
# That misdiagnosed the two most common local-run failures: a paid-plan voice
# (402) and a bad key (401), neither of which is temporary and neither of which
# retrying will fix.
# ---------------------------------------------------------------------------

def _provider_raising(status_code: int | None, upstream: str = "upstream text"):
    from app.providers.voice.base import VoiceProviderError
    provider = MagicMock()
    provider.synthesize = AsyncMock(
        side_effect=VoiceProviderError(
            f"ElevenLabs TTS returned {status_code}",
            status_code=status_code,
            upstream_detail=upstream,
        )
    )
    return provider


def _speak(provider):
    client = _client_with_voice_override(provider)
    with _auth_patches()[0], _auth_patches()[1], _settings_patch():
        return client.post("/api/speak", json={"text": SAMPLE_TEXT}, headers=AUTH_HEADER)


def test_speak_402_reports_paid_plan_requirement():
    """The exact failure hit locally: a professional voice on a free plan."""
    resp = _speak(_provider_raising(
        402, "Free users cannot use library voices via the API."
    ))
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "paid plan" in detail.lower()
    assert "ELEVENLABS_VOICE_ID" in detail


def test_speak_401_reports_api_key_problem():
    resp = _speak(_provider_raising(401, "invalid api key"))
    assert resp.status_code == 502
    assert "ELEVENLABS_API_KEY" in resp.json()["detail"]


def test_speak_404_reports_voice_not_found():
    resp = _speak(_provider_raising(404, "voice not found"))
    assert resp.status_code == 502
    assert "ELEVENLABS_VOICE_ID" in resp.json()["detail"]


def test_speak_429_maps_to_429_not_502():
    """A rate limit is retryable, so it must not look like a gateway failure."""
    resp = _speak(_provider_raising(429, "too many requests"))
    assert resp.status_code == 429
    assert "rate limited" in resp.json()["detail"].lower()


def test_speak_unknown_status_falls_back_to_502():
    resp = _speak(_provider_raising(500, "internal server error"))
    assert resp.status_code == 502
    assert "temporarily unavailable" in resp.json()["detail"].lower()


def test_speak_timeout_without_status_falls_back_to_502():
    """Transport failures carry no status and must still be handled."""
    resp = _speak(_provider_raising(None, None))
    assert resp.status_code == 502
    assert "temporarily unavailable" in resp.json()["detail"].lower()


def test_speak_never_leaks_upstream_error_text():
    """Provider error bodies are for logs, not for the browser."""
    resp = _speak(_provider_raising(
        402, "Free users cannot use library voices. request_id=871dc3179904b877"
    ))
    body = resp.text
    assert "request_id" not in body
    assert "871dc3179904b877" not in body


def test_speak_never_leaks_api_key_on_error():
    resp = _speak(_provider_raising(401, "key test-xi-key-SECRET rejected"))
    assert "test-xi-key-SECRET" not in resp.text
