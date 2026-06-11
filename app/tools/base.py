import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolContext:
    user_id: uuid.UUID
    credentials: dict[str, Any]
    permissions: set[str]


class ToolDefinition(ABC):
    name: str
    description: str
    input_model: type[BaseModel]
    required_permission: str
    credential_fields: list[str] = []
    risk: str = "low"

    @abstractmethod
    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
            "required_permission": self.required_permission,
            "credential_fields": self.credential_fields,
            "risk": self.risk,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list(self) -> list[dict[str, Any]]:
        return [tool.metadata() for tool in self._tools.values()]


registry = ToolRegistry()
