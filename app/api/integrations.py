import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import BrowserSession, ToolConnection, User
from app.schemas import BrowserActionRequest, IntegrationExecuteRequest
from app.security import (
    create_purpose_token,
    decode_access_token,
    decode_purpose_token,
    decrypt_credentials,
    encrypt_credentials,
    get_current_user,
)
from app.services.browserbase import browserbase_ready, create_browserbase_session, run_browser_action
from app.services.google_integration import (
    authorization_url,
    encoded_email,
    exchange_code,
    google_redirect_uri,
    google_ready,
    google_request,
    save_google_connection,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def integration_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    try:
        detail = exc.response.json().get("error", {}).get("message") or exc.response.text
    except ValueError:
        detail = exc.response.text
    return HTTPException(status_code=502, detail=detail[:500] or "External integration failed")


async def integration_user(
    authorization: Annotated[str | None, Header(alias="Authorization")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing integration token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = decode_purpose_token(token, "elevenlabs-tool")
    except ValueError:
        try:
            user_id = decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid integration token") from exc
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


@router.get("/google/status")
async def google_status(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    connection = await db.scalar(
        select(ToolConnection).where(
            ToolConnection.user_id == user.id,
            ToolConnection.tool_name == "google",
            ToolConnection.enabled.is_(True),
        )
    )
    return {
        "configured": google_ready(),
        "connected": bool(connection),
        "redirect_uri": google_redirect_uri() if get_settings().public_url else "",
        "youtube_configured": bool(get_settings().youtube_api_key),
    }


@router.get("/google/connect")
async def google_connect(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    if not google_ready():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    state = create_purpose_token(user.id, "google-oauth", minutes=10)
    return {
        "authorization_url": authorization_url(state, user.email),
        "redirect_uri": google_redirect_uri(),
    }


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    try:
        user_id = decode_purpose_token(state, "google-oauth")
        tokens = await exchange_code(code)
        await save_google_connection(db, user_id, tokens)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=400, detail="Unable to connect Google") from exc
    return RedirectResponse(url="/?google=connected")


@router.post("/execute/{tool_name}")
async def execute_integration(
    tool_name: str,
    payload: IntegrationExecuteRequest,
    user: Annotated[User, Depends(integration_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    args = payload.arguments
    try:
        return await _execute_integration(tool_name, args, payload.confirmed, user, db)
    except httpx.HTTPStatusError as exc:
        raise integration_http_error(exc) from exc


async def _execute_integration(
    tool_name: str,
    args: dict[str, Any],
    confirmed: bool,
    user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    if tool_name == "gmail_search":
        data = await google_request(
            db,
            user.id,
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": args.get("query", "in:inbox"), "maxResults": min(int(args.get("max_results", 10)), 20)},
        )
        return {"message_ids": [item["id"] for item in data.get("messages", [])]}
    if tool_name == "gmail_read":
        return await google_request(
            db,
            user.id,
            "GET",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{args['message_id']}",
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
        )
    if tool_name in {"gmail_draft", "gmail_send"}:
        if tool_name == "gmail_send" and not confirmed:
            raise HTTPException(status_code=409, detail="Confirmation required before sending email")
        raw = encoded_email(args["to"], args["subject"], args["body"])
        if tool_name == "gmail_draft":
            return await google_request(
                db,
                user.id,
                "POST",
                "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
                json={"message": {"raw": raw}},
            )
        return await google_request(
            db,
            user.id,
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json={"raw": raw},
        )
    if tool_name == "calendar_events":
        return await google_request(
            db,
            user.id,
            "GET",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={
                "timeMin": args.get("time_min", datetime.now(timezone.utc).isoformat()),
                "maxResults": min(int(args.get("max_results", 20)), 50),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
    if tool_name == "calendar_create":
        if not confirmed:
            raise HTTPException(status_code=409, detail="Confirmation required before creating a meeting")
        event = {
            "summary": args["summary"],
            "description": args.get("description", ""),
            "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", "Asia/Kolkata")},
            "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", "Asia/Kolkata")},
            "attendees": [{"email": email} for email in args.get("attendees", [])],
        }
        if args.get("google_meet"):
            event["conferenceData"] = {
                "createRequest": {"requestId": str(uuid.uuid4()), "conferenceSolutionKey": {"type": "hangoutsMeet"}}
            }
        return await google_request(
            db,
            user.id,
            "POST",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={"sendUpdates": "all", "conferenceDataVersion": 1},
            json=event,
        )
    if tool_name == "youtube_search":
        settings = get_settings()
        if not settings.youtube_api_key:
            raise HTTPException(status_code=503, detail="YouTube API is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "key": settings.youtube_api_key,
                    "part": "snippet",
                    "type": "video",
                    "videoEmbeddable": "true",
                    "safeSearch": "strict",
                    "q": args["query"],
                    "maxResults": min(int(args.get("max_results", 5)), 10),
                },
            )
            response.raise_for_status()
            data = response.json()
        return {
            "videos": [
                {
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "embed_url": f"https://www.youtube-nocookie.com/embed/{item['id']['videoId']}?autoplay=1",
                }
                for item in data.get("items", [])
            ]
        }
    raise HTTPException(status_code=404, detail="Unknown integration tool")


@router.post("/browser/session")
async def create_browser_session(
    user: Annotated[User, Depends(integration_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    if not browserbase_ready():
        raise HTTPException(status_code=503, detail="Browserbase is not configured")
    session = await create_browserbase_session(str(user.id))
    row = BrowserSession(
        user_id=user.id,
        provider_session_id=session["id"],
        encrypted_connection=encrypt_credentials({"connect_url": session["connectUrl"]}),
        live_view_url=session["debuggerFullscreenUrl"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"session_id": str(row.id), "live_view_url": row.live_view_url}


@router.post("/browser/{session_id}/action")
async def browser_action(
    session_id: uuid.UUID,
    payload: BrowserActionRequest,
    user: Annotated[User, Depends(integration_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    confirmed: bool = Query(default=False),
) -> dict[str, Any]:
    session = await db.get(BrowserSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Browser session not found")
    if payload.action in {"click", "type", "press"} and not confirmed:
        raise HTTPException(status_code=409, detail="Confirmation required for interactive browser actions")
    connection = decrypt_credentials(session.encrypted_connection)
    try:
        return await run_browser_action(
            connection["connect_url"],
            payload.action,
            url=payload.url,
            selector=payload.selector,
            text=payload.text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
