from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.schemas import LocalAgentCommandRequest
from app.security import get_current_user
from app.services.local_agent import handle_local_agent_command, local_agent_status

router = APIRouter(prefix="/local-agent", tags=["local-agent"])


@router.get("/status")
async def status(_user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    return local_agent_status()


@router.post("/command")
async def command(
    payload: LocalAgentCommandRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        return await handle_local_agent_command(payload.prompt, user.email)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
