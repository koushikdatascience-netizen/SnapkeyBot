import json
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ToolConnection
from app.services.llm import create_chat_completion, is_llm_configured
from app.services.tool_executor import execute_tool
from app.tools import registry


async def run_agent(db: AsyncSession, user_id: uuid.UUID, prompt: str) -> dict[str, Any]:
    if is_llm_configured():
        return await _run_llm_agent(db, user_id, prompt)
    return await _run_deterministic_agent(db, user_id, prompt)


async def _run_llm_agent(db: AsyncSession, user_id: uuid.UUID, prompt: str) -> dict[str, Any]:
    connected = set(
        (await db.scalars(
            select(ToolConnection.tool_name).where(
                ToolConnection.user_id == user_id, ToolConnection.enabled.is_(True)
            )
        )).all()
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": metadata["name"],
                "description": metadata["description"],
                "parameters": metadata["input_schema"],
            },
        }
        for metadata in registry.list()
        if metadata["name"] in connected
    ]
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are Snapkey Assistant. Use connected tools when useful. "
                "Never claim a tool action succeeded unless its result confirms it."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    calls: list[dict[str, Any]] = []
    for _ in range(get_settings().llm_max_steps):
        completion = await create_chat_completion(messages, tools)
        message = completion["choices"][0]["message"]
        messages.append(message)
        if not message.get("tool_calls"):
            return {"message": message.get("content") or "", "tool_calls": calls}
        for call in message["tool_calls"]:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
                result = await execute_tool(db, user_id, name, arguments)
                calls.append({"name": name, "arguments": arguments, "result": result})
                content = json.dumps(result, default=str)
            except Exception as exc:
                content = json.dumps({"error": str(exc)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    return {"message": "I stopped after reaching the tool-call step limit.", "tool_calls": calls}


async def _run_deterministic_agent(db: AsyncSession, user_id: uuid.UUID, prompt: str) -> dict[str, Any]:
    """Offline fallback used when no real LLM provider is configured."""
    calculator = re.search(r"(?:calculate|calc)\s+(.+)", prompt, re.IGNORECASE)
    if calculator:
        result = await execute_tool(db, user_id, "calculator", {"expression": calculator.group(1)})
        return {"message": f"The result is {result['value']}.", "tool_calls": [result]}

    echo = re.search(r"echo\s+(.+)", prompt, re.IGNORECASE)
    if echo:
        result = await execute_tool(db, user_id, "echo", {"text": echo.group(1)})
        return {"message": result["text"], "tool_calls": [result]}

    return {
        "message": "I am ready. Connect a tool, then try `calculate 20 * 4` or `echo hello`.",
        "tool_calls": [],
    }
