from app.tools.base import ToolContext, ToolDefinition, registry
from app.tools.builtin import CalculatorTool, EchoTool
from app.tools.google import CalendarEventsTool, GmailSearchTool
from app.tools.local_os import ListWorkspaceTool, SystemInfoTool

registry.register(EchoTool())
registry.register(CalculatorTool())
registry.register(GmailSearchTool())
registry.register(CalendarEventsTool())
registry.register(SystemInfoTool())
registry.register(ListWorkspaceTool())

__all__ = ["ToolContext", "ToolDefinition", "registry"]
