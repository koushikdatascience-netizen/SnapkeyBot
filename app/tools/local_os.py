import platform
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import ToolContext, ToolDefinition


WORKSPACE = Path(__file__).resolve().parents[2]


def _workspace_path(relative_path: str) -> Path:
    path = (WORKSPACE / relative_path).resolve()
    if path != WORKSPACE and WORKSPACE not in path.parents:
        raise ValueError("Path must stay inside the Snapkey Assistant workspace")
    return path


class SystemInfoInput(BaseModel):
    pass


class SystemInfoTool(ToolDefinition):
    name = "system_info"
    description = "Read basic information about the computer running Snapkey Assistant."
    input_model = SystemInfoInput
    required_permission = "os:read"

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "workspace": str(WORKSPACE),
        }


class ListWorkspaceInput(BaseModel):
    path: str = Field(default=".", max_length=500)


class ListWorkspaceTool(ToolDefinition):
    name = "list_workspace"
    description = "List files inside the Snapkey Assistant project. Cannot access paths outside the project."
    input_model = ListWorkspaceInput
    required_permission = "os:read"

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        path = _workspace_path(self.input_model.model_validate(arguments).path)
        if not path.is_dir():
            raise ValueError("Path is not a directory")
        return {"path": str(path.relative_to(WORKSPACE)), "entries": [item.name for item in list(path.iterdir())[:100]]}
