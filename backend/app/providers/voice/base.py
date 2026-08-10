"""
VoiceProvider abstract base class — Phase 7.

Mirrors the LLMProvider pattern: abstract base class + concrete implementation
(ElevenLabsProvider) + factory function (get_voice_provider).

Two methods:
  - transcribe(audio_bytes, content_type) -> TranscribeResult
  - synthesize(text, voice_id) -> bytes (MP3)

All implementations must raise VoiceProviderError on API failure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class VoiceProviderError(Exception):
    """Raised when a voice provider API call fails or configuration is missing."""


@dataclass
class TranscribeResult:
    transcript: str
    duration_seconds: float | None = field(default=None)


class VoiceProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str,
    ) -> TranscribeResult:
        """
        Send audio bytes to the STT service.

        content_type is the MIME type of the audio (e.g. "audio/webm",
        "audio/wav", "audio/mpeg"). Passed through to the provider as-is.

        Returns TranscribeResult with transcript and optional duration_seconds.
        Raises VoiceProviderError on API error.
        """

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
    ) -> bytes:
        """
        Synthesize text to speech using the TTS service.

        voice_id identifies the voice to use. Model is configured via
        environment variable (never passed by caller).

        Returns raw MP3 bytes.
        Raises VoiceProviderError on API error.
        """
