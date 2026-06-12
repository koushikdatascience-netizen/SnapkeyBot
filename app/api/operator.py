import secrets
from collections import defaultdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.telegram import accept_operator_update

router = APIRouter(prefix="/operator", tags=["operator"])
presenters: dict[str, set[WebSocket]] = defaultdict(set)
operators: dict[str, set[WebSocket]] = defaultdict(set)


async def notify_operators(session_id: str) -> None:
    stale = []
    for websocket in operators[session_id]:
        try:
            await websocket.send_json({"type": "status", "presenters": len(presenters[session_id])})
        except Exception:
            stale.append(websocket)
    for websocket in stale:
        operators[session_id].discard(websocket)


@router.websocket("/demo/{session_id}")
async def demo_director_socket(websocket: WebSocket, session_id: str, role: str = "presenter", key: str = "") -> None:
    settings = get_settings()
    if role == "operator":
        if not settings.demo_operator_secret or not secrets.compare_digest(key, settings.demo_operator_secret):
            await websocket.close(code=1008, reason="Invalid operator key")
            return
        await websocket.accept()
        operators[session_id].add(websocket)
        await notify_operators(session_id)
        try:
            while True:
                command = await websocket.receive_json()
                if command.get("type") != "scene":
                    continue
                scene = command.get("scene")
                if scene not in {"intro", "sales", "calendar", "camera1", "camera2", "thankyou"}:
                    continue
                stale = []
                for presenter in presenters[session_id]:
                    try:
                        await presenter.send_json({"type": "scene", "scene": scene})
                    except Exception:
                        stale.append(presenter)
                for presenter in stale:
                    presenters[session_id].discard(presenter)
                await websocket.send_json(
                    {"type": "delivered", "scene": scene, "presenters": len(presenters[session_id])}
                )
        except WebSocketDisconnect:
            operators[session_id].discard(websocket)
            if not operators[session_id]:
                operators.pop(session_id, None)
            return

    await websocket.accept()
    presenters[session_id].add(websocket)
    await notify_operators(session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        presenters[session_id].discard(websocket)
        if not presenters[session_id]:
            presenters.pop(session_id, None)
        await notify_operators(session_id)


@router.post("/telegram", include_in_schema=False)
async def telegram_webhook(
    update: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.concierge_mode or not settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not secret or not secrets.compare_digest(secret, settings.telegram_webhook_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")
    return {"accepted": await accept_operator_update(db, update)}
