import uuid

import pytest

from app.tools.base import ToolContext
from app.tools.builtin import CalculatorTool
from app.tools.local_os import ListWorkspaceTool


@pytest.mark.asyncio
async def test_calculator_executes_basic_arithmetic():
    context = ToolContext(user_id=uuid.uuid4(), credentials={}, permissions={"calculator:execute"})
    result = await CalculatorTool().execute(context, {"expression": "(20 + 2) * 4"})
    assert result["value"] == 88


@pytest.mark.asyncio
async def test_calculator_rejects_code_execution():
    context = ToolContext(user_id=uuid.uuid4(), credentials={}, permissions={"calculator:execute"})
    with pytest.raises(ValueError):
        await CalculatorTool().execute(context, {"expression": "__import__('os').getcwd()"})


@pytest.mark.asyncio
async def test_workspace_tool_rejects_paths_outside_project():
    context = ToolContext(user_id=uuid.uuid4(), credentials={}, permissions={"os:read"})
    with pytest.raises(ValueError):
        await ListWorkspaceTool().execute(context, {"path": ".."})
