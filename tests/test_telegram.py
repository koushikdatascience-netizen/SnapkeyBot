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
    assert task.result == {
        "message": "Your requested report is ready.",
        "source": "concierge",
        "attachments": [],
    }
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


@pytest.mark.asyncio
async def test_webhook_readiness_requires_config(monkeypatch):
    from app.services.telegram import telegram_webhook_ready

    monkeypatch.setenv("CONCIERGE_MODE", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    get_settings.cache_clear()
    assert await telegram_webhook_ready() is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_plain_operator_message_answers_latest_pending_task(monkeypatch):
    from app.services import telegram

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

    async def fake_telegram_request(_method, _payload):
        return {}

    monkeypatch.setattr(telegram, "_telegram_request", fake_telegram_request)
    accepted = await accept_operator_update(
        db,
        {"message": {"chat": {"id": 12345}, "text": "Hello from Telegram"}},
    )

    assert accepted is True
    assert task.result["message"] == "Hello from Telegram"
    assert task.status == TaskStatus.succeeded
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_operator_attachment_is_added_to_result(monkeypatch):
    from app.services import telegram

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

    async def fake_download(_task_id, _attachment):
        return {"name": "answer.pdf", "content_type": "application/pdf", "path": "uploads/answer.pdf"}

    monkeypatch.setattr(telegram, "_download_operator_attachment", fake_download)
    accepted = await accept_operator_update(
        db,
        {
            "message": {
                "chat": {"id": 12345},
                "caption": "Here is the file.",
                "document": {"file_id": "file-1", "file_name": "answer.pdf", "mime_type": "application/pdf"},
                "reply_to_message": {"message_id": 99},
            }
        },
    )

    assert accepted is True
    assert task.result["attachments"][0]["name"] == "answer.pdf"
    assert task.result["attachments"][0]["url"].endswith("/attachments/0")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_operator_command_adds_interactive_workspace(monkeypatch):
    from app.services import telegram

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

    async def fake_telegram_request(_method, _payload):
        return {}

    monkeypatch.setattr(telegram, "_telegram_request", fake_telegram_request)
    accepted = await accept_operator_update(
        db,
        {
            "message": {
                "chat": {"id": 12345},
                "text": "/products\ntitle: Top chairs\nitem: Chair One | Rs 4,999 | 4.7 | Best value",
                "reply_to_message": {"message_id": 99},
            }
        },
    )

    assert accepted is True
    assert task.result["message"] == "Top chairs"
    assert task.result["presentation"]["type"] == "products"
    assert task.result["presentation"]["items"][0]["name"] == "Chair One"
    get_settings.cache_clear()
