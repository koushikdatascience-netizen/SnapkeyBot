from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ToolConnection, User
from app.schemas import ToolConnectRequest
from app.security import encrypt_credentials, get_current_user
from app.tools import registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    connected = set(
        (await db.scalars(select(ToolConnection.tool_name).where(ToolConnection.user_id == user.id))).all()
    )
    return [{**tool, "connected": tool["name"] in connected} for tool in registry.list()]


@router.put("/{tool_name}")
async def connect_tool(
    tool_name: str,
    payload: ToolConnectRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        tool = registry.get(tool_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    connection = await db.scalar(
        select(ToolConnection).where(ToolConnection.user_id == user.id, ToolConnection.tool_name == tool_name)
    )
    permissions = payload.permissions or [tool.required_permission]
    if connection:
        connection.encrypted_credentials = encrypt_credentials(payload.credentials)
        connection.permissions = permissions
        connection.enabled = True
    else:
        db.add(
            ToolConnection(
                user_id=user.id,
                tool_name=tool_name,
                encrypted_credentials=encrypt_credentials(payload.credentials),
                permissions=permissions,
            )
        )
    await db.commit()
    return {"connected": True, "tool_name": tool_name, "permissions": permissions}

