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
    """
    Raised when a voice provider API call fails or configuration is missing.

    Carries the upstream HTTP status (when the failure came from an API
    response) so routes can distinguish a caller-fixable problem — expired key,
    plan limit, rate limit — from a genuine provider outage. Without this, every
    failure collapsed into an opaque 502 and had to be diagnosed by calling the
    provider by hand.

    Attributes:
        status_code: upstream HTTP status, or None for timeouts/transport errors.
        upstream_detail: provider's own error text. Logged server-side; never
            returned to the browser verbatim.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        upstream_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.upstream_detail = upstream_detail


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
