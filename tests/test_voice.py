from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app.main import app


class FakeSpeechResponse:
    async def aiter_bytes(self):
        yield b"first-audio-chunk"
        yield b"second-audio-chunk"


def test_voice_endpoint_requires_authentication():
    with TestClient(app) as client:
        response = client.post("/api/voice/speech", json={"text": "Hello"})
    assert response.status_code == 401


def test_voice_endpoint_streams_audio(monkeypatch):
    from app.api import voice

    @asynccontextmanager
    async def fake_stream(_text):
        yield FakeSpeechResponse()

    monkeypatch.setattr(voice, "voice_ready", lambda: True)
    monkeypatch.setattr(voice, "stream_speech", fake_stream)
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/signup",
            json={"email": "voice@example.com", "password": "password123"},
        ).json()["access_token"]
        response = client.post(
            "/api/voice/speech",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Hello from Snapkey"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"first-audio-chunksecond-audio-chunk"
