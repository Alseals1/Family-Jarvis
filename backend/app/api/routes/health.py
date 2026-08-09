from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
        "demo_mode": settings.is_demo,
        "db": "configured" if settings.supabase_url else "missing",
    }
