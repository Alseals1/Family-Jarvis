from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.llm import router as llm_router
from app.api.routes.family_members import router as family_members_router
from app.api.routes.important_dates import router as important_dates_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.calendar import router as calendar_router
from app.api.routes.chat import router as chat_router
from app.api.routes.briefing import router as briefing_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.voice import router as voice_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start APScheduler on startup, stop on shutdown."""
    # Only start the scheduler when not in test/demo mode (guards against real
    # DB calls in unit tests that don't set up Supabase).
    # The scheduler is always importable — only started when env is configured.
    scheduler = None
    if not settings.is_demo:
        try:
            from app.jobs.scheduler import build_scheduler, start_scheduler, stop_scheduler
            from app.db.supabase import get_supabase_admin
            scheduler = build_scheduler(db_admin=get_supabase_admin())
            start_scheduler(scheduler)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Scheduler failed to start — running without background jobs"
            )
    yield
    if scheduler is not None:
        try:
            from app.jobs.scheduler import stop_scheduler
            stop_scheduler(scheduler)
        except Exception:
            pass


app = FastAPI(
    title="Family JARVIS",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(llm_router)
app.include_router(family_members_router)
app.include_router(important_dates_router)
app.include_router(preferences_router)
app.include_router(calendar_router)
app.include_router(chat_router)
app.include_router(briefing_router)
app.include_router(notifications_router)
app.include_router(voice_router)
