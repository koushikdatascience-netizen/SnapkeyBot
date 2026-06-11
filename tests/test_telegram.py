import uuid
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.models import TaskStatus
from app.services.telegram import accept_operator_update


class FakeDb:
    def __init__(self, dispatch, task):
        self.dispatch = dispatch
        self.task = task
        self.added = []
        self.commits = 0

    async def scalar(self, _query):
        return self.dispatch

    async def get(self, _model, _id):
        return self.task

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_operator_reply_completes_matching_task(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OPERATOR_CHAT_ID", "12345")
    get_settings.cache_clear()
    task = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        status=TaskStatus.queued,
        result=None,
    )
    dispatch = SimpleNamespace(task_id=task.id, replied_at=None)
    db = FakeDb(dispatch, task)

    accepted = await accept_operator_update(
        db,
        {
            "message": {
                "chat": {"id": 12345},
                "text": "Your requested report is ready.",
                "reply_to_message": {"message_id": 99},
            }
        },
    )

    assert accepted is True
    assert task.status == TaskStatus.succeeded
    assert task.result == {"message": "Your requested report is ready.", "source": "concierge"}
    assert dispatch.replied_at is not None
    assert db.commits == 1
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_operator_reply_rejects_unknown_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OPERATOR_CHAT_ID", "12345")
    get_settings.cache_clear()
    db = FakeDb(None, None)
    accepted = await accept_operator_update(db, {"message": {"chat": {"id": 999}, "text": "No"}})
    assert accepted is False
    assert db.commits == 0
    get_settings.cache_clear()
