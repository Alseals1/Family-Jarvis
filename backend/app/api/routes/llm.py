from fastapi import APIRouter, HTTPException
from app.config import get_settings
from app.providers.llm.openrouter import get_llm_provider
from app.providers.llm.base import Message

router = APIRouter()


@router.post("/api/llm/test")
async def test_llm_connection():
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404)

    provider = get_llm_provider()
    response = await provider.complete(
        messages=[Message(role="user", content="Reply with exactly: JARVIS_OK")],
        model=settings.openrouter_model_fast,
        temperature=0.0,
    )
    return {"status": "ok", "response": response, "model": settings.openrouter_model_fast}
