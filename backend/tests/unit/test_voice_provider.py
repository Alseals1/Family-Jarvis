"""
Unit tests for VoiceProvider ABC, ElevenLabsProvider, and get_voice_provider factory.

All ElevenLabs HTTP calls are mocked — no real network calls.

14 tests:
 1. test_transcribe_sends_audio_bytes_to_scribe_endpoint
 2. test_transcribe_includes_api_key_header
 3. test_transcribe_passes_content_type_to_scribe
 4. test_transcribe_returns_transcript_text
 5. test_transcribe_returns_duration_seconds_when_provided
 6. test_transcribe_raises_voice_provider_error_on_api_failure
 7. test_transcribe_raises_voice_provider_error_on_non_200
 8. test_synthesize_sends_text_to_tts_endpoint
 9. test_synthesize_includes_api_key_header
10. test_synthesize_uses_configured_voice_id
11. test_synthesize_uses_configured_tts_model
12. test_synthesize_returns_audio_bytes
13. test_synthesize_raises_voice_provider_error_on_api_failure
14. test_get_voice_provider_raises_when_api_key_missing
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_API_KEY = "test-xi-key-abc123"
FAKE_VOICE_ID = "voice-german-001"
FAKE_TTS_MODEL = "eleven_multilingual_v2"
FAKE_STT_MODEL = "scribe_v1"
FAKE_AUDIO_BYTES = b"RIFF\x00\x00\x00\x00WAVEfmt "
FAKE_TRANSCRIPT = "What is happening on Friday?"
FAKE_MP3_BYTES = b"\xff\xfb\x90\x00" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider() -> "ElevenLabsProvider":
    from app.providers.voice.elevenlabs import ElevenLabsProvider
    return ElevenLabsProvider(
        api_key=FAKE_API_KEY,
        tts_model=FAKE_TTS_MODEL,
        stt_model=FAKE_STT_MODEL,
    )


def _mock_httpx_response(status_code: int, json_data: dict | None = None, content: bytes = b"") -> MagicMock:
    """Return a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("no JSON")
    return resp


def _async_client_context(mock_response: MagicMock) -> MagicMock:
    """Build a mock async context manager for httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


# ---------------------------------------------------------------------------
# Transcribe tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_sends_audio_bytes_to_scribe_endpoint():
    """transcribe() POSTs to the ElevenLabs speech-to-text endpoint."""
    resp = _mock_httpx_response(200, {"text": FAKE_TRANSCRIPT})
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        result = await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")

    mock_client = ctx.__aenter__.return_value
    call_args = mock_client.post.call_args
    assert "speech-to-text" in call_args.args[0]


@pytest.mark.asyncio
async def test_transcribe_includes_api_key_header():
    """transcribe() includes xi-api-key header with the configured API key."""
    resp = _mock_httpx_response(200, {"text": FAKE_TRANSCRIPT})
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")

    mock_client = ctx.__aenter__.return_value
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["xi-api-key"] == FAKE_API_KEY


@pytest.mark.asyncio
async def test_transcribe_passes_content_type_to_scribe():
    """transcribe() passes the content_type to Scribe as the file MIME type."""
    resp = _mock_httpx_response(200, {"text": FAKE_TRANSCRIPT})
    ctx = _async_client_context(resp)
    content_type = "audio/webm"

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.transcribe(FAKE_AUDIO_BYTES, content_type)

    mock_client = ctx.__aenter__.return_value
    call_kwargs = mock_client.post.call_args.kwargs
    # files is a dict: {"file": (filename, bytes, content_type)}
    file_tuple = call_kwargs["files"]["file"]
    assert file_tuple[2] == content_type


@pytest.mark.asyncio
async def test_transcribe_returns_transcript_text():
    """transcribe() returns a TranscribeResult with the transcript text."""
    resp = _mock_httpx_response(200, {"text": FAKE_TRANSCRIPT})
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        result = await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")

    assert result.transcript == FAKE_TRANSCRIPT


@pytest.mark.asyncio
async def test_transcribe_returns_duration_seconds_when_provided():
    """transcribe() includes duration_seconds from Scribe response when present."""
    resp = _mock_httpx_response(200, {"text": FAKE_TRANSCRIPT, "audio_duration": 3.7})
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        result = await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")

    assert result.duration_seconds == pytest.approx(3.7)


@pytest.mark.asyncio
async def test_transcribe_raises_voice_provider_error_on_api_failure():
    """transcribe() raises VoiceProviderError when httpx raises an exception."""
    import httpx as _httpx
    from app.providers.voice.base import VoiceProviderError

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_httpx.HTTPError("connection failed"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        with pytest.raises(VoiceProviderError):
            await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")


@pytest.mark.asyncio
async def test_transcribe_raises_voice_provider_error_on_non_200():
    """transcribe() raises VoiceProviderError when Scribe returns non-200 status."""
    from app.providers.voice.base import VoiceProviderError

    resp = _mock_httpx_response(401, None)
    resp.json.side_effect = None
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        with pytest.raises(VoiceProviderError) as exc_info:
            await provider.transcribe(FAKE_AUDIO_BYTES, "audio/wav")

    assert "401" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Synthesize tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_sends_text_to_tts_endpoint():
    """synthesize() POSTs to the ElevenLabs text-to-speech endpoint."""
    resp = _mock_httpx_response(200, content=FAKE_MP3_BYTES)
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.synthesize("Hello world.", FAKE_VOICE_ID)

    mock_client = ctx.__aenter__.return_value
    url = mock_client.post.call_args.args[0]
    assert "text-to-speech" in url


@pytest.mark.asyncio
async def test_synthesize_includes_api_key_header():
    """synthesize() includes xi-api-key header with the configured API key."""
    resp = _mock_httpx_response(200, content=FAKE_MP3_BYTES)
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.synthesize("Hello world.", FAKE_VOICE_ID)

    mock_client = ctx.__aenter__.return_value
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["xi-api-key"] == FAKE_API_KEY


@pytest.mark.asyncio
async def test_synthesize_uses_configured_voice_id():
    """synthesize() uses the voice_id argument in the TTS endpoint URL."""
    resp = _mock_httpx_response(200, content=FAKE_MP3_BYTES)
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.synthesize("Hello.", FAKE_VOICE_ID)

    mock_client = ctx.__aenter__.return_value
    url = mock_client.post.call_args.args[0]
    assert FAKE_VOICE_ID in url


@pytest.mark.asyncio
async def test_synthesize_uses_configured_tts_model():
    """synthesize() sends the configured tts_model in the JSON payload."""
    resp = _mock_httpx_response(200, content=FAKE_MP3_BYTES)
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        await provider.synthesize("Hello.", FAKE_VOICE_ID)

    mock_client = ctx.__aenter__.return_value
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["json"]["model_id"] == FAKE_TTS_MODEL


@pytest.mark.asyncio
async def test_synthesize_returns_audio_bytes():
    """synthesize() returns the raw audio bytes from the TTS response."""
    resp = _mock_httpx_response(200, content=FAKE_MP3_BYTES)
    ctx = _async_client_context(resp)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        result = await provider.synthesize("Hello.", FAKE_VOICE_ID)

    assert result == FAKE_MP3_BYTES


@pytest.mark.asyncio
async def test_synthesize_raises_voice_provider_error_on_api_failure():
    """synthesize() raises VoiceProviderError when httpx raises an exception."""
    import httpx as _httpx
    from app.providers.voice.base import VoiceProviderError

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_httpx.HTTPError("timeout"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.providers.voice.elevenlabs.httpx.AsyncClient", return_value=ctx):
        provider = _make_provider()
        with pytest.raises(VoiceProviderError):
            await provider.synthesize("Hello.", FAKE_VOICE_ID)


# ---------------------------------------------------------------------------
# Factory test
# ---------------------------------------------------------------------------

def test_get_voice_provider_raises_when_api_key_missing():
    """get_voice_provider() raises VoiceProviderError when ELEVENLABS_API_KEY is empty."""
    from app.providers.voice.base import VoiceProviderError

    mock_settings = MagicMock()
    mock_settings.elevenlabs_api_key = ""
    mock_settings.elevenlabs_tts_model = FAKE_TTS_MODEL
    mock_settings.elevenlabs_stt_model = FAKE_STT_MODEL

    # get_settings is imported at the top of app.providers.voice — patch it there
    with patch("app.providers.voice.get_settings", return_value=mock_settings):
        from app.providers.voice import get_voice_provider
        with pytest.raises(VoiceProviderError):
            get_voice_provider()
