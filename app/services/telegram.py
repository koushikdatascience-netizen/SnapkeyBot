from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AgentTask, Message, OperatorDispatch, TaskStatus


def validate_telegram_config() -> None:
    settings = get_settings()
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
            "TELEGRAM_OPERATOR_CHAT_ID": settings.telegram_operator_chat_id,
            "TELEGRAM_WEBHOOK_SECRET": settings.telegram_webhook_secret,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Concierge mode requires: {', '.join(missing)}")


async def _telegram_request(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram request failed"))
        return data["result"]


async def dispatch_to_operator(db: AsyncSession, task: AgentTask, user_email: str) -> None:
    validate_telegram_config()
    settings = get_settings()
    message = await _telegram_request(
        "sendMessage",
        {
            "chat_id": settings.telegram_operator_chat_id,
            "text": (
                "New Snapkey concierge request\n\n"
                f"Client: {user_email}\n"
                f"Session: {task.session_id}\n"
                f"Task: {task.id}\n\n"
                f"{task.prompt[:3000]}\n\n"
                "Reply directly to this Telegram message to answer the client."
            ),
        },
    )
    db.add(
        OperatorDispatch(
            task_id=task.id,
            telegram_chat_id=int(message["chat"]["id"]),
            telegram_message_id=int(message["message_id"]),
        )
    )
    await db.commit()


async def accept_operator_update(db: AsyncSession, update: dict[str, Any]) -> bool:
    settings = get_settings()
    message = update.get("message") or update.get("edited_message")
    if not message or str(message.get("chat", {}).get("id")) != settings.telegram_operator_chat_id:
        return False
    reply_to_id = message.get("reply_to_message", {}).get("message_id")
    reply_text = message.get("text")
    if not reply_to_id or not reply_text:
        return False
    dispatch = await db.scalar(
        select(OperatorDispatch)
        .where(OperatorDispatch.telegram_message_id == int(reply_to_id))
        .with_for_update()
    )
    if not dispatch or dispatch.replied_at:
        return False
    task = await db.get(AgentTask, dispatch.task_id)
    if not task or task.status in {TaskStatus.succeeded, TaskStatus.failed}:
        return False

    task.result = {"message": reply_text, "source": "concierge"}
    task.status = TaskStatus.succeeded
    dispatch.replied_at = datetime.now(timezone.utc)
    db.add(Message(user_id=task.user_id, session_id=task.session_id, role="assistant", content=reply_text))
    await db.commit()
    return True
