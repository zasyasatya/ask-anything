from typing import Any

from .base import Tool, ToolContext, ToolResult
from .calculator import CALCULATOR
from .diagrams import CREATE_DIAGRAM
from .fetch_url import FETCH_URL
from .web_search import WEB_SEARCH

ALL_TOOLS: list[Tool] = [WEB_SEARCH, FETCH_URL, CREATE_DIAGRAM, CALCULATOR]

_BY_NAME = {t.name: t for t in ALL_TOOLS}


def tool_schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in ALL_TOOLS]


def get_tool(name: str) -> Tool | None:
    return _BY_NAME.get(name)


__all__ = [
    "ALL_TOOLS",
    "Tool",
    "ToolContext",
    "ToolResult",
    "tool_schemas",
    "get_tool",
]
