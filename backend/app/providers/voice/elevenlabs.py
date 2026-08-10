"""
ElevenLabsProvider — Phase 7.

Concrete VoiceProvider implementation using ElevenLabs Scribe (STT) and TTS.

All HTTP calls via httpx.AsyncClient.
API key comes from settings — never from caller or request body.

STT endpoint:  POST https://api.elevenlabs.io/v1/speech-to-text
TTS endpoint:  POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}

Security:
  - ELEVENLABS_API_KEY is read from settings at construction time.
  - Voice ID is passed by the caller (route reads it from settings).
  - TTS model is read from settings.
  - No key is ever returned to callers.
"""

from __future__ import annotations

import httpx

from app.providers.voice.base import TranscribeResult, VoiceProvider, VoiceProviderError

_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsProvider(VoiceProvider):
    """
    Implements VoiceProvider using ElevenLabs Scribe (STT) and TTS.

    Args:
        api_key: ElevenLabs API key — from settings, never hardcoded.
        tts_model: TTS model ID (default: eleven_multilingual_v2).
        stt_model: Scribe STT model ID (default: scribe_v1).
    """

    def __init__(
        self,
        api_key: str,
        tts_model: str = "eleven_multilingual_v2",
        stt_model: str = "scribe_v1",
    ) -> None:
        self._api_key = api_key
        self._tts_model = tts_model
        self._stt_model = stt_model

    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str,
    ) -> TranscribeResult:
        """
        Send audio bytes to ElevenLabs Scribe.

        content_type is passed as the file MIME type in the multipart upload.
        Returns TranscribeResult with transcript and duration_seconds (if provided).
        Raises VoiceProviderError on API error.
        """
        # Derive a sensible filename extension from content_type so Scribe
        # can identify the format (it also inspects bytes, but a good filename helps).
        ext = _ext_from_content_type(content_type)
        filename = f"audio.{ext}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    _STT_URL,
                    headers={"xi-api-key": self._api_key},
                    files={
                        "file": (filename, audio_bytes, content_type),
                    },
                    data={"model_id": self._stt_model},
                    timeout=60.0,
                )
        except httpx.TimeoutException as exc:
            raise VoiceProviderError("ElevenLabs Scribe request timed out") from exc
        except httpx.HTTPError as exc:
            raise VoiceProviderError(f"ElevenLabs Scribe HTTP error: {exc}") from exc

        if response.status_code != 200:
            raise VoiceProviderError(
                f"ElevenLabs Scribe returned {response.status_code}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise VoiceProviderError("ElevenLabs Scribe returned non-JSON response") from exc

        transcript = data.get("text", "")
        duration_seconds: float | None = data.get("audio_duration") or data.get("duration_seconds")

        return TranscribeResult(
            transcript=str(transcript),
            duration_seconds=float(duration_seconds) if duration_seconds is not None else None,
        )

    async def synthesize(
        self,
        text: str,
        voice_id: str,
    ) -> bytes:
        """
        Call ElevenLabs TTS for the given text and voice ID.

        Returns raw MP3 bytes.
        Model is configured via ELEVENLABS_TTS_MODEL env var.
        Raises VoiceProviderError on API error.
        """
        url = _TTS_URL.format(voice_id=voice_id)
        payload = {
            "text": text,
            "model_id": self._tts_model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "xi-api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                )
        except httpx.TimeoutException as exc:
            raise VoiceProviderError("ElevenLabs TTS request timed out") from exc
        except httpx.HTTPError as exc:
            raise VoiceProviderError(f"ElevenLabs TTS HTTP error: {exc}") from exc

        if response.status_code != 200:
            raise VoiceProviderError(
                f"ElevenLabs TTS returned {response.status_code}"
            )

        return response.content


def _ext_from_content_type(content_type: str) -> str:
    """Map a MIME type to a file extension. Falls back to 'bin'."""
    _MAP = {
        "audio/webm": "webm",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/mp4": "mp4",
        "audio/x-m4a": "m4a",
    }
    return _MAP.get(content_type.split(";")[0].strip().lower(), "bin")
