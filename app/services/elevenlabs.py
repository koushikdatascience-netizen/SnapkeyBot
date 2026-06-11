from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.config import get_settings


def voice_ready() -> bool:
    settings = get_settings()
    return bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id)


def live_agent_ready() -> bool:
    settings = get_settings()
    return bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id)


async def create_conversation_token(participant_name: str) -> str:
    settings = get_settings()
    if not live_agent_ready():
        raise RuntimeError("Live agent is not configured")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://api.elevenlabs.io/v1/convai/conversation/token",
            params={
                "agent_id": settings.elevenlabs_agent_id,
                "participant_name": participant_name[:100],
            },
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
        response.raise_for_status()
        return response.json()["token"]


@asynccontextmanager
async def stream_speech(text: str) -> AsyncIterator[httpx.Response]:
    settings = get_settings()
    if not voice_ready():
        raise RuntimeError("Voice mode is not configured")
    payload = {
        "text": text[: settings.tts_max_characters],
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
            "style": 0.15,
            "use_speaker_boost": True,
        },
    }
    if settings.elevenlabs_language_code:
        payload["language_code"] = settings.elevenlabs_language_code
    params = {"output_format": settings.elevenlabs_output_format}
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}/stream",
            params=params,
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            yield response
