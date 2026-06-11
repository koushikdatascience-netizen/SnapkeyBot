import uuid
import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import AgentSession, AgentTask, Message, TaskStatus, User
from app.schemas import TaskResponse
from app.security import decode_access_token, get_current_user
from app.services.telegram import dispatch_to_operator
from app.worker import _run_agent_task, run_agent_task

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


@router.post("", response_model=TaskResponse, status_code=202)
async def chat(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    prompt: Annotated[str, Form(max_length=20_000)] = "",
    attachment: Annotated[UploadFile | None, File()] = None,
) -> TaskResponse:
    prompt = prompt.strip()
    if not prompt and not attachment:
        raise HTTPException(status_code=422, detail="Enter a message or attach a file")
    file_data: tuple[str, bytes, str] | None = None
    if attachment:
        content = await attachment.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Attachment is too large")
        file_data = (
            Path(attachment.filename or "attachment").name,
            content,
            attachment.content_type or "application/octet-stream",
        )
    display_prompt = prompt or f"Shared attachment: {file_data[0]}"
    session = AgentSession(user_id=user.id, title=display_prompt[:80])
    db.add(session)
    await db.flush()
    db.add(Message(user_id=user.id, session_id=session.id, role="user", content=display_prompt))
    task = AgentTask(user_id=user.id, session_id=session.id, prompt=display_prompt)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    if settings.concierge_mode:
        background_tasks.add_task(_dispatch_concierge_task, task.id, user.email, file_data)
    elif settings.task_always_eager:
        await _run_agent_task(task.id)
    else:
        run_agent_task.delay(str(task.id))
    return TaskResponse(id=task.id, status=task.status)


async def _dispatch_concierge_task(
    task_id: uuid.UUID,
    user_email: str,
    file_data: tuple[str, bytes, str] | None,
) -> None:
    async with SessionLocal() as db:
        task = await db.get(AgentTask, task_id)
        if not task:
            return
        try:
            await dispatch_to_operator(db, task, user_email, file_data)
        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = f"Unable to reach the concierge operator: {exc}"
            await db.commit()


@router.get("/tasks/{task_id}/attachments/{attachment_index}")
async def get_task_attachment(
    task_id: uuid.UUID,
    attachment_index: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    task = await db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    attachments = (task.result or {}).get("attachments", [])
    if attachment_index < 0 or attachment_index >= len(attachments):
        raise HTTPException(status_code=404, detail="Attachment not found")
    attachment = attachments[attachment_index]
    path = Path(attachment.get("_path", ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment is no longer available")
    return FileResponse(path, media_type=attachment["content_type"], filename=attachment["name"])


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    task = await db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(id=task.id, status=task.status, result=_public_result(task.result), error=task.error)


@router.websocket("/ws/tasks/{task_id}")
async def stream_task(websocket: WebSocket, task_id: uuid.UUID, token: str) -> None:
    try:
        user_id = decode_access_token(token)
    except ValueError:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            async with SessionLocal() as db:
                task = await db.get(AgentTask, task_id)
                if not task or task.user_id != user_id:
                    await websocket.close(code=1008)
                    return
                await websocket.send_json(
                    TaskResponse(id=task.id, status=task.status, result=_public_result(task.result), error=task.error).model_dump(
                        mode="json"
                    )
                )
                if task.status.value in {"succeeded", "failed"}:
                    return
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


def _public_result(result: dict | None) -> dict | None:
    if not result:
        return result
    cleaned = dict(result)
    cleaned["attachments"] = [
        {key: value for key, value in attachment.items() if key != "_path"}
        for attachment in result.get("attachments", [])
    ]
    return cleaned
