from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.models import User
from app.schemas import DesktopActionRequest, LocalCommandRequest, SpeechRequest
from app.security import get_current_user
from app.services.local_voice import (
    control_desktop_app,
    local_turn,
    local_voice_ready,
    local_voice_status,
    handle_local_command,
    preview_purchase_document,
    synthesize_wav,
)

router = APIRouter(prefix="/local-voice", tags=["local-voice"])


@router.get("/status")
async def status(_user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    return local_voice_status()


@router.post("/command")
async def command(
    payload: LocalCommandRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        return await handle_local_command(payload.prompt, user.email)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/speech")
async def local_speech(
    payload: SpeechRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        audio = await synthesize_wav(payload.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/wav")


@router.post("/turn")
async def turn(
    user: Annotated[User, Depends(get_current_user)],
    audio: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    settings = get_settings()
    if not local_voice_ready():
        raise HTTPException(status_code=503, detail="Local voice runtime is not ready")
    payload = await audio.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Audio utterance is too large")
    if not payload:
        raise HTTPException(status_code=422, detail="Audio utterance is empty")
    try:
        return await local_turn(payload, user.email)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/desktop-action")
async def desktop_action(
    payload: DesktopActionRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        result = await control_desktop_app(payload.app, payload.action, confirmed=payload.confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result.get("status") == "confirmation_required":
        raise HTTPException(status_code=409, detail=f"Confirmation required before closing {payload.app}")
    return result


@router.post("/purchase-preview")
async def purchase_preview(
    _user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=422, detail="Choose a PDF or CSV purchase invoice")
    max_upload_bytes = get_settings().max_upload_bytes
    payload = await file.read(max_upload_bytes + 1)
    if len(payload) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="Purchase document is too large")
    try:
        return preview_purchase_document(file.filename, payload)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
