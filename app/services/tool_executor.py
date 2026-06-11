import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolConnection
from app.security import decrypt_credentials
from app.tools import ToolContext, registry


async def execute_tool(
    db: AsyncSession, user_id: uuid.UUID, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    connection = await db.scalar(
        select(ToolConnection).where(
            ToolConnection.user_id == user_id,
            ToolConnection.tool_name == tool_name,
            ToolConnection.enabled.is_(True),
        )
    )
    if not connection:
        raise PermissionError(f"Tool '{tool_name}' is not connected")
    tool = registry.get(tool_name)
    permissions = set(connection.permissions)
    if tool.required_permission not in permissions:
        raise PermissionError(f"Missing permission: {tool.required_permission}")
    context = ToolContext(user_id, decrypt_credentials(connection.encrypted_credentials), permissions)
    return await tool.execute(context, arguments)

