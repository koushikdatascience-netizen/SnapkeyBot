import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ToolConnection
from app.security import decrypt_credentials, encrypt_credentials

GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def google_ready() -> bool:
    settings = get_settings()
    return bool(settings.google_client_id and settings.google_client_secret and settings.public_url)


def google_redirect_uri() -> str:
    settings = get_settings()
    return f"{settings.public_url.rstrip('/')}/api/integrations/google/callback"


def authorization_url(state: str, login_hint: str = "") -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": google_redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def save_google_connection(db: AsyncSession, user_id: Any, tokens: dict[str, Any]) -> None:
    connection = await db.scalar(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_name == "google",
        )
    )
    existing = decrypt_credentials(connection.encrypted_credentials) if connection else {}
    credentials = {
        **existing,
        **tokens,
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)) - 60)
        ).isoformat(),
    }
    permissions = ["gmail:read", "gmail:draft", "gmail:send", "calendar:read", "calendar:write"]
    if connection:
        connection.encrypted_credentials = encrypt_credentials(credentials)
        connection.permissions = permissions
        connection.enabled = True
    else:
        db.add(
            ToolConnection(
                user_id=user_id,
                tool_name="google",
                encrypted_credentials=encrypt_credentials(credentials),
                permissions=permissions,
            )
        )
    await db.commit()


async def google_access_token(db: AsyncSession, user_id: Any) -> str:
    settings = get_settings()
    connection = await db.scalar(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_name == "google",
            ToolConnection.enabled.is_(True),
        )
    )
    if not connection:
        raise PermissionError("Connect Google first")
    credentials = decrypt_credentials(connection.encrypted_credentials)
    expires_at = datetime.fromisoformat(credentials.get("expires_at", "1970-01-01T00:00:00+00:00"))
    if expires_at > datetime.now(timezone.utc) and credentials.get("access_token"):
        return credentials["access_token"]
    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        raise PermissionError("Reconnect Google to refresh access")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        refreshed = response.json()
    await save_google_connection(db, user_id, {**refreshed, "refresh_token": refresh_token})
    return refreshed["access_token"]


async def google_request(
    db: AsyncSession,
    user_id: Any,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = await google_access_token(db, user_id)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method, url, params=params, json=json, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json() if response.content else {}


def encoded_email(to: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
