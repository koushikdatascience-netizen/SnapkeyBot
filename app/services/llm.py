from typing import Any

import httpx

from app.config import get_settings


PROVIDER_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-4.1-mini"),
}


def is_llm_configured() -> bool:
    settings = get_settings()
    return settings.llm_provider in PROVIDER_DEFAULTS and bool(settings.llm_api_key)


async def create_chat_completion(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    if settings.llm_provider not in PROVIDER_DEFAULTS:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
    default_url, default_model = PROVIDER_DEFAULTS[settings.llm_provider]
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    if settings.llm_provider == "openrouter":
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        headers["X-Title"] = settings.openrouter_app_name

    payload: dict[str, Any] = {
        "model": settings.llm_model or default_model,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{(settings.llm_base_url or default_url).rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()
