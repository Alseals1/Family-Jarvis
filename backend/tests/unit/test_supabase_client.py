from unittest.mock import patch, MagicMock

REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
}


def test_get_supabase_uses_anon_key():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()

        mock_client = MagicMock()
        with patch("app.db.supabase.create_client", return_value=mock_client) as mock_create:
            from app.db.supabase import get_supabase
            get_supabase.cache_clear()

            client = get_supabase()

            mock_create.assert_called_once_with("https://test.supabase.co", "test-anon-key")
            assert client is mock_client

        get_supabase.cache_clear()
        get_settings.cache_clear()


def test_get_supabase_admin_uses_service_role_key():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()

        mock_client = MagicMock()
        with patch("app.db.supabase.create_client", return_value=mock_client) as mock_create:
            from app.db.supabase import get_supabase_admin
            get_supabase_admin.cache_clear()

            client = get_supabase_admin()

            mock_create.assert_called_once_with("https://test.supabase.co", "test-service-key")
            assert client is mock_client

        get_supabase_admin.cache_clear()
        get_settings.cache_clear()


def test_supabase_clients_are_different():
    """Anon and admin clients must be distinct — different keys."""
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()

        call_args = []

        def capture_create(url, key):
            m = MagicMock()
            call_args.append(key)
            return m

        with patch("app.db.supabase.create_client", side_effect=capture_create):
            from app.db.supabase import get_supabase, get_supabase_admin
            get_supabase.cache_clear()
            get_supabase_admin.cache_clear()

            get_supabase()
            get_supabase_admin()

        assert "test-anon-key" in call_args
        assert "test-service-key" in call_args
        assert call_args[0] != call_args[1]

        get_supabase.cache_clear()
        get_supabase_admin.cache_clear()
        get_settings.cache_clear()


def test_health_includes_db_field():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            data = c.get("/health").json()
        assert "db" in data
        assert data["db"] == "configured"
        get_settings.cache_clear()
