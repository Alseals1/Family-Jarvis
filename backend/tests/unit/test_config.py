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
    # _env_file=None is required: Settings declares env_file=".env", so a plain
    # Settings() reads the developer's local .env and this asserts nothing about
    # the code default. It passed for months only because the two happened to
    # agree.
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings(_env_file=None)
        assert s.openrouter_model_manager == "google/gemma-4-26b-a4b-it:free"
        assert s.openrouter_model_fast == "google/gemma-4-26b-a4b-it:free"


def test_model_defaults_are_free_tier():
    """Defaults must stay on a :free model — a paid default bills silently."""
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import Settings
        s = Settings(_env_file=None)
        for field in (
            s.openrouter_model_manager,
            s.openrouter_model_organizer,
            s.openrouter_model_chef,
            s.openrouter_model_planner,
            s.openrouter_model_fast,
        ):
            assert field.endswith(":free")


def test_env_file_overrides_code_default():
    """Local .env must win over the built-in default."""
    with patch.dict("os.environ", {**REQUIRED_ENV, "OPENROUTER_MODEL_MANAGER": "acme/custom-model"}, clear=True):
        from app.config import Settings
        s = Settings(_env_file=None)
        assert s.openrouter_model_manager == "acme/custom-model"
