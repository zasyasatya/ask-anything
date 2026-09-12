"""calculator tool — AST-safe arithmetic."""
from __future__ import annotations

import ast
import operator
from typing import Any

from .base import Tool, ToolContext, ToolResult

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr: str) -> float:
    node = ast.parse(expr, mode="eval")

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_eval(n.operand))
        raise ValueError(f"unsupported expression: {ast.dump(n)}")

    return _eval(node)


async def run_calculator(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    expr = str(args.get("expression", ""))
    try:
        value = safe_eval(expr)
    except Exception as exc:  # noqa: BLE001 - user input, report back to agent
        return ToolResult(summary=f"calculator error: {exc}",
                          data={"error": str(exc)})
    pretty = int(value) if float(value).is_integer() else round(value, 8)
    return ToolResult(summary=f"{expr} = {pretty}",
                      data={"expression": expr, "result": pretty})


CALCULATOR = Tool(
    name="calculator",
    description="Evaluate an arithmetic expression (+ - * / // % **).",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
    run=run_calculator,
)
