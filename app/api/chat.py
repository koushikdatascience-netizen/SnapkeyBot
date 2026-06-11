import uuid
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import AgentSession, AgentTask, Message, TaskStatus, User
from app.schemas import ChatRequest, TaskResponse
from app.security import decode_access_token, get_current_user
from app.services.telegram import dispatch_to_operator
from app.worker import _run_agent_task, run_agent_task

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


@router.post("", response_model=TaskResponse, status_code=202)
async def chat(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    session = await db.get(AgentSession, payload.session_id) if payload.session_id else None
    if session and session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session:
        session = AgentSession(user_id=user.id, title=payload.prompt[:80])
        db.add(session)
        await db.flush()
    db.add(Message(user_id=user.id, session_id=session.id, role="user", content=payload.prompt))
    task = AgentTask(user_id=user.id, session_id=session.id, prompt=payload.prompt)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    if settings.concierge_mode:
        try:
            await dispatch_to_operator(db, task, user.email)
        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = f"Unable to reach the concierge operator: {exc}"
            await db.commit()
    elif settings.task_always_eager:
        await _run_agent_task(task.id)
    else:
        run_agent_task.delay(str(task.id))
    return TaskResponse(id=task.id, status=task.status)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    task = await db.get(AgentTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(id=task.id, status=task.status, result=task.result, error=task.error)


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
                    TaskResponse(id=task.id, status=task.status, result=task.result, error=task.error).model_dump(
                        mode="json"
                    )
                )
                if task.status.value in {"succeeded", "failed"}:
                    return
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
