import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import TaskStatus


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ToolConnectRequest(BaseModel):
    credentials: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    session_id: uuid.UUID | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None


class AppConfigResponse(BaseModel):
    concierge_mode: bool
    concierge_ready: bool
    max_upload_bytes: int
    voice_ready: bool
    live_agent_ready: bool
    local_voice_ready: bool = False
    local_voice_enabled: bool = False
    local_voice_silence_ms: int = 650
    local_voice_min_speech_ms: int = 350
    monitoring_camera_urls: list[str] = Field(default_factory=list)
    monitoring_screen_url: str = ""


class LiveConversationTokenResponse(BaseModel):
    token: str
    tool_token: str
    voice_id: str = ""
    language: str = "hi"


class IntegrationExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class BrowserActionRequest(BaseModel):
    action: str
    url: str | None = None
    selector: str | None = None
    text: str | None = None


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)


class DesktopActionRequest(BaseModel):
    action: str = Field(pattern="^(open|focus|minimize|close)$")
    app: str = Field(default="madhushala", pattern="^[a-zA-Z0-9_-]{1,50}$")
    confirmed: bool = False


class LocalCommandRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)
