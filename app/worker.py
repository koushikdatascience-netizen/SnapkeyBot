import asyncio
import uuid

from celery import Celery

from app.config import get_settings
from app.database import SessionLocal
from app.models import AgentTask, Message, TaskStatus
from app.services.agent import run_agent

settings = get_settings()
celery_app = Celery("snapkey", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.task_always_eager,
)


@celery_app.task(
    name="run_agent_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_agent_task(task_id: str) -> None:
    asyncio.run(_run_agent_task(uuid.UUID(task_id)))


async def _run_agent_task(task_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        task = await db.get(AgentTask, task_id)
        if not task:
            return
        task.status = TaskStatus.running
        await db.commit()
        try:
            task.result = await run_agent(db, task.user_id, task.prompt)
            task.status = TaskStatus.succeeded
            db.add(Message(user_id=task.user_id, session_id=task.session_id, role="assistant", content=task.result["message"]))
        except Exception as exc:
            task.status = TaskStatus.failed
            task.error = str(exc)
        await db.commit()
