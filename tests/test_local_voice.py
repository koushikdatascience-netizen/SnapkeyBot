from fastapi.testclient import TestClient

from app.main import app
from app.services import local_voice


def test_local_report_intent_is_allowlisted():
    assert local_voice._report_intent("show low stock today") == {
        "report_name": "low_stock",
        "days": 1,
        "limit": 20,
        "chart": "",
    }
    assert local_voice._report_intent("tell me a joke") is None


def test_local_monitoring_intent_selects_camera():
    workspace = local_voice._monitoring_workspace("show camera 2")
    assert workspace["type"] == "monitoring"
    assert workspace["selected_camera"] == 2


def test_madhushala_action_requires_explicit_erp_name():
    assert local_voice._desktop_action("open Madhushala") == ("madhushala", "open")
    assert local_voice._desktop_action("close the current report") == ("", "")


def test_purchase_csv_preview_does_not_commit():
    result = local_voice.preview_purchase_csv(b"item,quantity,rate\nExample Product,2,125\n")
    assert result["workspace"]["title"] == "Purchase import preview"
    assert result["workspace"]["total"] == 250


def test_purchase_document_rejects_unknown_file_type():
    try:
        local_voice.preview_purchase_document("invoice.xlsx", b"data")
    except ValueError as exc:
        assert "PDF or CSV" in str(exc)
    else:
        raise AssertionError("Unsupported purchase document should be rejected")


def test_local_voice_turn_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/local-voice/turn",
            files={"audio": ("utterance.wav", b"wav", "audio/wav")},
        )
    assert response.status_code == 401


def test_local_voice_turn_returns_local_result(monkeypatch):
    from app.api import local_voice as api

    async def fake_turn(audio, email):
        assert audio == b"wav"
        assert email == "local@example.com"
        return {
            "transcript": "show sales",
            "reply": "Sales are ready.",
            "workspace": {"type": "report"},
            "audio_base64": "AA==",
            "audio_content_type": "audio/wav",
        }

    monkeypatch.setattr(api, "local_voice_ready", lambda: True)
    monkeypatch.setattr(api, "local_turn", fake_turn)
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/signup",
            json={"email": "local@example.com", "password": "password123"},
        ).json()["access_token"]
        response = client.post(
            "/api/local-voice/turn",
            headers={"Authorization": f"Bearer {token}"},
            files={"audio": ("utterance.wav", b"wav", "audio/wav")},
        )
    assert response.status_code == 200
    assert response.json()["workspace"]["type"] == "report"
