import pytest
from unittest.mock import patch


REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "OPENROUTER_API_KEY": "sk-or-test-key",
    "ELEVENLABS_API_KEY": "test-el-key",
}


def test_settings_load_from_env():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings()
        assert s.supabase_url == "https://test.supabase.co"
        assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert s.jarvis_demo is True
        assert s.app_env == "development"


def test_cors_origins_list_splits_correctly():
    env = {**REQUIRED_ENV, "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173"}
    with patch.dict("os.environ", env, clear=True):
        from app.config import Settings
        s = Settings()
        assert s.cors_origins_list == ["http://localhost:3000", "http://localhost:5173"]


def test_is_demo_true_by_default():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings()
        assert s.is_demo is True


def test_is_production_false_in_development():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings()
        assert s.is_production is False


def test_model_defaults_to_gemma_free():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings()
        assert s.openrouter_model_manager == "google/gemma-4-31b-it:free"
        assert s.openrouter_model_fast == "google/gemma-4-31b-it:free"
