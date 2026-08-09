from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.llm import router as llm_router
from app.api.routes.family_members import router as family_members_router
from app.api.routes.important_dates import router as important_dates_router
from app.api.routes.preferences import router as preferences_router

settings = get_settings()

app = FastAPI(
    title="Family JARVIS",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
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
