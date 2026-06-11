from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models import User
from app.schemas import LiveConversationTokenResponse, SpeechRequest
from app.security import create_purpose_token, get_current_user
from app.services.elevenlabs import create_conversation_token, live_agent_ready, stream_speech, voice_ready

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/conversation-token", response_model=LiveConversationTokenResponse)
async def conversation_token(
    user: Annotated[User, Depends(get_current_user)],
) -> LiveConversationTokenResponse:
    if not live_agent_ready():
        raise HTTPException(status_code=503, detail="Live voice agent is not configured")
    try:
        token = await create_conversation_token(str(user.id))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to start the live voice agent") from exc
    return LiveConversationTokenResponse(
        token=token,
        tool_token=create_purpose_token(user.id, "elevenlabs-tool", minutes=30),
    )


@router.post("/speech")
async def speech(
    payload: SpeechRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    settings = get_settings()
    if not voice_ready():
        raise HTTPException(status_code=503, detail="Voice mode is not configured")
    if len(payload.text) > settings.tts_max_characters:
        raise HTTPException(status_code=422, detail="Reply is too long to speak")

    async def audio_stream():
        try:
            async with stream_speech(payload.text) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.HTTPStatusError as exc:
            # The response has already started; ending the stream lets the UI use its fallback.
            return

    return StreamingResponse(audio_stream(), media_type="audio/mpeg")
