"""
Voice API routes — Phase 7.

POST /api/listen — Speech-to-text (STT) via ElevenLabs Scribe
POST /api/speak  — Text-to-speech (TTS) via ElevenLabs

Security:
  - JWT required for both routes (get_current_user dependency).
  - ELEVENLABS_API_KEY is never returned in any response.
  - ELEVENLABS_VOICE_ID comes from settings only — never from request body.
  - Audio bytes are treated as data (forwarded to Scribe as-is).
  - Transcript is treated as user message data — not as instructions.
    Prompt injection defense is the Manager Agent's responsibility
    (already in place from Phase 4). No execution of transcript content here.

Design decisions (Phase 7 plan):
  - /api/listen: no server-side transcoding — ElevenLabs Scribe handles format.
  - /api/speak: returns full MP3 bytes (no streaming in Phase 7 MVP).
  - Voice ID is env-var-only — no per-user voice selection in MVP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, field_validator

from app.api.middleware.auth import get_current_user
from app.providers.voice import get_voice_provider
from app.providers.voice.base import VoiceProvider, VoiceProviderError

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ListenResponse(BaseModel):
    transcript: str
    duration_seconds: float | None = None


class SpeakRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def sanitize(cls, v: str) -> str:
        """Strip null bytes and leading/trailing whitespace. Truncate at 5000 chars."""
        v = v.strip().replace("\x00", "")
        if not v:
            raise ValueError("text must not be empty after sanitization")
        return v[:5000]


# ---------------------------------------------------------------------------
# POST /api/listen — STT
# ---------------------------------------------------------------------------

@router.post("/listen", response_model=ListenResponse)
async def listen(
    audio: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    voice: VoiceProvider = Depends(get_voice_provider),
) -> ListenResponse:
    """
    Accept an audio file upload, send to ElevenLabs Scribe, return transcript.

    Request: multipart/form-data with field 'audio' (webm/wav/mp3/ogg/flac).
    Response: {"transcript": str, "duration_seconds": float | None}

    Security:
    - JWT required.
    - Audio bytes are forwarded to Scribe as-is (no storage, no logging of audio).
    - Transcript is returned as data — callers must pass it through the Manager
      Agent which has prompt injection defense from Phase 4.
    - ELEVENLABS_API_KEY is never in the response.
    """
    audio_bytes = await audio.read()
    content_type = audio.content_type or "application/octet-stream"

    try:
        result = await voice.transcribe(audio_bytes, content_type)
    except VoiceProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Speech-to-text service temporarily unavailable.",
        ) from exc

    return ListenResponse(
        transcript=result.transcript,
        duration_seconds=result.duration_seconds,
    )


# ---------------------------------------------------------------------------
# POST /api/speak — TTS
# ---------------------------------------------------------------------------

@router.post("/speak")
async def speak(
    body: SpeakRequest,
    user: dict = Depends(get_current_user),
    voice: VoiceProvider = Depends(get_voice_provider),
) -> Response:
    """
    Accept text, synthesize via ElevenLabs TTS, return MP3 audio bytes.

    Request: {"text": str}
    Response: audio/mpeg bytes (full MP3, not streamed)

    Security:
    - JWT required.
    - Voice ID comes from ELEVENLABS_VOICE_ID env var — never from request body.
    - ELEVENLABS_API_KEY is never in the response body or headers.
    - Text is sanitized (null bytes stripped, truncated at 5000 chars) by
      the SpeakRequest validator before reaching the provider.
    """
    from app.config import get_settings
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id

    try:
        audio_bytes = await voice.synthesize(body.text, voice_id)
    except VoiceProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Text-to-speech service temporarily unavailable.",
        ) from exc

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
    )
