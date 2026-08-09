import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "OPENROUTER_API_KEY": "sk-or-test-key",
    "ELEVENLABS_API_KEY": "test-el-key",
    "JARVIS_DEMO": "true",
    "APP_ENV": "development",
}


@pytest.fixture
def client():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        # Clear lru_cache so patched env is used
        from app.config import get_settings
        get_settings.cache_clear()

        from app.main import app
        with TestClient(app) as c:
            yield c

        get_settings.cache_clear()


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_shape(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "env" in data
    assert "demo_mode" in data


def test_health_demo_mode_true(client):
    data = client.get("/health").json()
    assert data["demo_mode"] is True


def test_health_env_is_development(client):
    data = client.get("/health").json()
    assert data["env"] == "development"
