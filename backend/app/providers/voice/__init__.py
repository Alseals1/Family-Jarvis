"""
Voice provider factory — Phase 7.

get_voice_provider() returns the configured VoiceProvider.
Reads ELEVENLABS_API_KEY from settings.
Raises VoiceProviderError if the key is missing.

Usage in FastAPI routes (dependency injection):
    voice: VoiceProvider = Depends(get_voice_provider)
"""

from __future__ import annotations

from app.config import get_settings
from app.providers.voice.base import VoiceProvider, VoiceProviderError, TranscribeResult
from app.providers.voice.elevenlabs import ElevenLabsProvider


def get_voice_provider() -> VoiceProvider:
    """
    Return the configured VoiceProvider.

    Reads ELEVENLABS_API_KEY, ELEVENLABS_TTS_MODEL, and ELEVENLABS_STT_MODEL
    from settings. Raises VoiceProviderError if the API key is missing or empty.
    """
    settings = get_settings()
    api_key = settings.elevenlabs_api_key

    if not api_key:
        raise VoiceProviderError(
            "ELEVENLABS_API_KEY is not configured. "
            "Set it in .env before using voice features."
        )

    return ElevenLabsProvider(
        api_key=api_key,
        tts_model=settings.elevenlabs_tts_model,
        stt_model=settings.elevenlabs_stt_model,
    )


__all__ = [
    "get_voice_provider",
    "VoiceProvider",
    "VoiceProviderError",
    "TranscribeResult",
    "ElevenLabsProvider",
]
