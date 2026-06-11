import ast
import operator
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import ToolContext, ToolDefinition


class EchoInput(BaseModel):
    text: str = Field(max_length=10_000)


class EchoTool(ToolDefinition):
    name = "echo"
    description = "Echo text back to the user. Useful for testing tool execution."
    input_model = EchoInput
    required_permission = "echo:execute"

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        values = self.input_model.model_validate(arguments)
        return {"text": values.text, "executed_for": str(context.user_id)}


class CalculatorInput(BaseModel):
    expression: str = Field(max_length=500)


class CalculatorTool(ToolDefinition):
    name = "calculator"
    description = "Evaluate a basic arithmetic expression."
    input_model = CalculatorInput
    required_permission = "calculator:execute"

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        expression = self.input_model.model_validate(arguments).expression
        return {"expression": expression, "value": _safe_calculate(expression)}


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def _safe_calculate(expression: str) -> int | float:
    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](evaluate(node.operand))
        raise ValueError("Only basic arithmetic is allowed")

    return evaluate(ast.parse(expression, mode="eval").body)

