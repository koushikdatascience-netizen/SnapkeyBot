import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TASK_ALWAYS_EAGER"] = "true"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_tenant_can_connect_and_execute_tool(client):
    token = client.post(
        "/api/auth/signup", json={"email": "one@example.com", "password": "password123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put("/api/tools/calculator", headers=headers, json={"credentials": {}, "permissions": []})
    assert response.status_code == 200

    task = client.post("/api/chat", headers=headers, data={"prompt": "calculate 20 * 4"}).json()
    result = client.get(f"/api/chat/tasks/{task['id']}", headers=headers)
    assert result.json()["result"]["message"] == "The result is 80."


def test_health_and_ui_are_served(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert "What can we move" in response.text


def test_live_agent_bundle_includes_universal_workspace_tools(client):
    response = client.get("/static/live-agent.js")
    assert response.status_code == 200
    assert "show_workspace" in response.text
    assert "request_confirmation" in response.text
    assert "run_integration" in response.text
    assert "start_browser" in response.text
    assert "retail_report" in response.text
    assert "Preparing live report" in response.text
    assert "Browser connection issue" in response.text
    assert "sendContextualUpdate" in response.text


def test_tenant_cannot_read_another_tenants_task(client):
    first = client.post(
        "/api/auth/signup", json={"email": "first@example.com", "password": "password123"}
    ).json()["access_token"]
    second = client.post(
        "/api/auth/signup", json={"email": "second@example.com", "password": "password123"}
    ).json()["access_token"]
    task = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {first}"},
        data={"prompt": "hello"},
    ).json()

    response = client.get(
        f"/api/chat/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {second}"},
    )
    assert response.status_code == 404


def test_concierge_mode_dispatches_without_running_agent(client, monkeypatch):
    from app.api import chat as chat_api

    dispatched = []

    async def fake_dispatch(_db, task, email, attachment=None):
        dispatched.append((task.id, email))

    monkeypatch.setattr(chat_api.settings, "concierge_mode", True)
    monkeypatch.setattr(chat_api, "dispatch_to_operator", fake_dispatch)
    token = client.post(
        "/api/auth/signup", json={"email": "concierge@example.com", "password": "password123"}
    ).json()["access_token"]
    response = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token}"},
        data={"prompt": "Prepare the demo summary"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert dispatched[0][1] == "concierge@example.com"


def test_chat_accepts_attachment(client, monkeypatch):
    from app.api import chat as chat_api

    dispatched = []

    async def fake_dispatch(_db, task, _email, attachment=None):
        dispatched.append((task.prompt, attachment))

    monkeypatch.setattr(chat_api.settings, "concierge_mode", True)
    monkeypatch.setattr(chat_api, "dispatch_to_operator", fake_dispatch)
    token = client.post(
        "/api/auth/signup", json={"email": "upload@example.com", "password": "password123"}
    ).json()["access_token"]
    response = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token}"},
        data={"prompt": "Review this"},
        files={"attachment": ("brief.txt", b"demo content", "text/plain")},
    )

    assert response.status_code == 202
    assert dispatched[0][1] == ("brief.txt", b"demo content", "text/plain")


def test_config_exposes_upload_limit(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["max_upload_bytes"] > 0
