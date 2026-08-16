import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


REQUIRED_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service",
    "OPENROUTER_API_KEY": "sk-or-test",
    "ELEVENLABS_API_KEY": "test-el",
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
}


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": content}}]
    }
    return mock


@pytest.mark.asyncio
async def test_complete_sends_correct_headers():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        captured = {}

        async def mock_post(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["json"] = kwargs.get("json", {})
            return _mock_response("hello")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            await provider.complete([Message(role="user", content="hi")], model="test-model")

        assert "Bearer sk-or-test" in captured["headers"]["Authorization"]
        assert captured["url"].endswith("/chat/completions")
        assert captured["json"]["model"] == "test-model"
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_complete_returns_content():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("JARVIS_OK"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            result = await provider.complete([Message(role="user", content="test")], model="m")

        assert result == "JARVIS_OK"
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_complete_structured_parses_json():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        payload = json.dumps({"name": "Alice", "age": 30})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response(payload))

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            result = await provider.complete_structured(
                [Message(role="user", content="give me data")],
                schema={"name": "string", "age": "number"},
                model="m",
            )

        assert result == {"name": "Alice", "age": 30}
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_complete_structured_strips_markdown_fences():
    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        fenced = '```json\n{"key": "value"}\n```'
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response(fenced))

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            result = await provider.complete_structured(
                [Message(role="user", content="test")],
                schema={},
                model="m",
            )

        assert result == {"key": "value"}
        get_settings.cache_clear()


# --- Free-tier rate limiting -------------------------------------------------
#
# The free-tier model returns 429 under light load. The provider raises a
# typed error carrying a user-facing message so the route can map it to 429.


def _mock_429_response() -> MagicMock:
    import httpx
    mock = MagicMock()
    mock.status_code = 429
    mock.request = MagicMock()
    mock.raise_for_status = MagicMock()
    return mock


@pytest.mark.asyncio
async def test_complete_raises_on_429():
    import httpx

    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_429_response())

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            with pytest.raises(httpx.HTTPStatusError) as exc:
                await provider.complete([Message(role="user", content="hi")], model="m")

        assert "thinking too fast" in str(exc.value)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_429_short_circuits_before_raise_for_status():
    """The 429 branch must fire before the generic raise_for_status path."""
    import httpx

    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        response = _mock_429_response()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete([Message(role="user", content="hi")], model="m")

        response.raise_for_status.assert_not_called()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_complete_structured_propagates_429():
    """Structured calls hit the same free-tier limit and must surface it too."""
    import httpx

    with patch.dict("os.environ", REQUIRED_ENV, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.providers.llm.openrouter import OpenRouterProvider
        from app.providers.llm.base import Message

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_429_response())

        with patch("httpx.AsyncClient", return_value=mock_client):
            provider = OpenRouterProvider()
            with pytest.raises(httpx.HTTPStatusError):
                await provider.complete_structured(
                    [Message(role="user", content="hi")], schema={}, model="m"
                )

        get_settings.cache_clear()
