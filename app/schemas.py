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
