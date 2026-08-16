from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # OpenRouter
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_manager: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_model_organizer: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_model_chef: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_model_planner: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_model_fast: str = "google/gemma-4-26b-a4b-it:free"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v1"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/calendar/callback/google"

    # Calendar token encryption
    calendar_encryption_key: str = ""

    # Application
    app_env: str = "development"
    jarvis_demo: bool = True
    jwt_secret: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    # Where the OAuth callback sends the browser once the flow completes.
    frontend_url: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_demo(self) -> bool:
        return self.jarvis_demo

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
