from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

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


async def telegram_webhook_ready() -> bool:
    settings = get_settings()
    if not (
        settings.concierge_mode
        and settings.telegram_bot_token
        and settings.telegram_operator_chat_id
        and settings.telegram_webhook_secret
    ):
        return False
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getWebhookInfo"
            )
            response.raise_for_status()
            info = response.json().get("result", {})
            return bool(info.get("url")) and not info.get("last_error_message")
    except (httpx.HTTPError, ValueError):
        return False


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


async def _telegram_file_request(
    method: str, payload: dict[str, Any], field: str, filename: str, content: bytes, content_type: str
) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}",
            data=payload,
            files={field: (filename, content, content_type)},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram file request failed"))
        return data["result"]


def _dispatch_text(task: AgentTask, user_email: str) -> str:
    return (
        "New Snapkey concierge request\n\n"
        f"Client: {user_email}\n"
        f"Session: {task.session_id}\n"
        f"Task: {task.id}\n"
        "Reply directly to this Telegram message to answer the client.\n\n"
        f"Request:\n{task.prompt[:2500]}"
    )


async def dispatch_to_operator(
    db: AsyncSession,
    task: AgentTask,
    user_email: str,
    attachment: tuple[str, bytes, str] | None = None,
) -> None:
    validate_telegram_config()
    settings = get_settings()
    text = _dispatch_text(task, user_email)
    if attachment:
        filename, content, content_type = attachment
        message = await _telegram_file_request(
            "sendDocument",
            {"chat_id": settings.telegram_operator_chat_id, "caption": text[:1024]},
            "document",
            filename,
            content,
            content_type,
        )
    else:
        message = await _telegram_request(
            "sendMessage",
            {"chat_id": settings.telegram_operator_chat_id, "text": text},
        )
    db.add(
        OperatorDispatch(
            task_id=task.id,
            telegram_chat_id=int(message["chat"]["id"]),
            telegram_message_id=int(message["message_id"]),
        )
    )
    await db.commit()


def _operator_attachment(message: dict[str, Any]) -> tuple[str, str, str] | None:
    if message.get("document"):
        item = message["document"]
        return item["file_id"], item.get("file_name", "attachment"), item.get("mime_type", "application/octet-stream")
    for key, fallback in (("voice", "voice.ogg"), ("audio", "audio"), ("video", "video.mp4"), ("animation", "animation.gif")):
        if message.get(key):
            item = message[key]
            return item["file_id"], item.get("file_name", fallback), item.get("mime_type", "application/octet-stream")
    if message.get("photo"):
        return message["photo"][-1]["file_id"], "photo.jpg", "image/jpeg"
    return None


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    return cleaned[:180] or "attachment"


async def _download_operator_attachment(task_id: Any, attachment: tuple[str, str, str]) -> dict[str, str]:
    settings = get_settings()
    file_id, filename, content_type = attachment
    file_info = await _telegram_request("getFile", {"file_id": file_id})
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_info['file_path']}"
        )
        response.raise_for_status()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    path = upload_dir / f"{task_id}-{safe_name}"
    path.write_bytes(response.content)
    return {"name": safe_name, "content_type": content_type, "path": str(path)}


async def accept_operator_update(db: AsyncSession, update: dict[str, Any]) -> bool:
    settings = get_settings()
    message = update.get("message") or update.get("edited_message")
    if not message or str(message.get("chat", {}).get("id")) != settings.telegram_operator_chat_id:
        return False
    reply_to_id = message.get("reply_to_message", {}).get("message_id")
    reply_text = message.get("text") or message.get("caption") or ""
    attachment = _operator_attachment(message)
    if not reply_text and not attachment:
        return False
    if reply_to_id:
        dispatch_query = select(OperatorDispatch).where(
            OperatorDispatch.telegram_message_id == int(reply_to_id)
        )
    else:
        dispatch_query = (
            select(OperatorDispatch)
            .where(
                OperatorDispatch.telegram_chat_id == int(settings.telegram_operator_chat_id),
                OperatorDispatch.replied_at.is_(None),
            )
            .order_by(OperatorDispatch.created_at.desc())
        )
    dispatch = await db.scalar(dispatch_query.with_for_update())
    if not dispatch or dispatch.replied_at:
        return False
    task = await db.get(AgentTask, dispatch.task_id)
    if not task or task.status in {TaskStatus.succeeded, TaskStatus.failed}:
        return False

    result: dict[str, Any] = {
        "message": reply_text or "Sent an attachment.",
        "source": "concierge",
        "attachments": [],
    }
    if attachment:
        saved = await _download_operator_attachment(task.id, attachment)
        result["attachments"].append(
            {
                "name": saved["name"],
                "content_type": saved["content_type"],
                "url": f"/api/chat/tasks/{task.id}/attachments/0",
                "_path": saved["path"],
            }
        )
    task.result = result
    task.status = TaskStatus.succeeded
    dispatch.replied_at = datetime.now(timezone.utc)
    db.add(Message(user_id=task.user_id, session_id=task.session_id, role="assistant", content=reply_text))
    await db.commit()
    try:
        await _telegram_request(
            "sendMessage",
            {
                "chat_id": settings.telegram_operator_chat_id,
                "text": f"Delivered to Snapkey client.\nTask: {task.id}",
            },
        )
    except httpx.HTTPError:
        pass
    return True
