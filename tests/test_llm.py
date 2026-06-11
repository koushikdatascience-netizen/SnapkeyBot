import pytest

from app.config import get_settings
from app.services import llm


def test_provider_defaults_require_an_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()
    assert llm.is_llm_configured() is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_openrouter_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            return Response()

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: Client())
    await llm.create_chat_completion([{"role": "user", "content": "hello"}], [])
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    get_settings.cache_clear()
