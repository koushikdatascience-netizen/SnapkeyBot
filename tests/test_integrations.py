import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def authenticated_client():
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/signup",
            json={"email": f"integrations-{uuid.uuid4()}@example.com", "password": "password123"},
        ).json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}


def test_gmail_send_requires_confirmation(authenticated_client):
    client, headers = authenticated_client
    response = client.post(
        "/api/integrations/execute/gmail_send",
        headers=headers,
        json={
            "arguments": {"to": "team@example.com", "subject": "Update", "body": "Ready."},
            "confirmed": False,
        },
    )
    assert response.status_code == 409
    assert "Confirmation required" in response.json()["detail"]


def test_calendar_create_requires_confirmation(authenticated_client):
    client, headers = authenticated_client
    response = client.post(
        "/api/integrations/execute/calendar_create",
        headers=headers,
        json={
            "arguments": {
                "summary": "Supplier call",
                "start": "2026-06-12T10:00:00+05:30",
                "end": "2026-06-12T10:30:00+05:30",
            },
            "confirmed": False,
        },
    )
    assert response.status_code == 409


def test_confirmed_calendar_create_calls_google(authenticated_client, monkeypatch):
    from app.api import integrations

    async def fake_google_request(_db, _user_id, method, url, **kwargs):
        assert method == "POST"
        assert url.endswith("/calendars/primary/events")
        assert kwargs["json"]["summary"] == "Supplier call"
        return {"id": "event-1", "htmlLink": "https://calendar.google.com/event"}

    monkeypatch.setattr(integrations, "google_request", fake_google_request)
    client, headers = authenticated_client
    response = client.post(
        "/api/integrations/execute/calendar_create",
        headers=headers,
        json={
            "arguments": {
                "summary": "Supplier call",
                "start": "2026-06-12T10:00:00+05:30",
                "end": "2026-06-12T10:30:00+05:30",
            },
            "confirmed": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == "event-1"


def test_confirmed_gmail_send_calls_google(authenticated_client, monkeypatch):
    from app.api import integrations

    async def fake_google_request(_db, _user_id, method, url, **kwargs):
        assert method == "POST"
        assert url.endswith("/messages/send")
        assert kwargs["json"]["raw"]
        return {"id": "message-1"}

    monkeypatch.setattr(integrations, "google_request", fake_google_request)
    client, headers = authenticated_client
    response = client.post(
        "/api/integrations/execute/gmail_send",
        headers=headers,
        json={
            "arguments": {"to": "team@example.com", "subject": "Update", "body": "Ready."},
            "confirmed": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == "message-1"


def test_purpose_token_cannot_access_normal_api(authenticated_client):
    from app.security import create_purpose_token, decode_access_token

    client, headers = authenticated_client
    normal_token = headers["Authorization"].removeprefix("Bearer ")
    user_id = decode_access_token(normal_token)
    tool_token = create_purpose_token(user_id, "elevenlabs-tool")
    response = client.get("/api/tools", headers={"Authorization": f"Bearer {tool_token}"})
    assert response.status_code == 401
