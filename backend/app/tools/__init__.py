from typing import Any

from .base import (
    SOURCE_LABELS,
    TOOL_SOURCES,
    Tool,
    ToolContext,
    ToolResult,
)
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


def tool_source(name: str) -> str:
    """Provenance class of a tool ("browser" | "diagram" | "compute").

    Unknown tool names are reported as "compute" — never silently as browser,
    so a hallucinated tool can't masquerade as web evidence.
    """
    tool = _BY_NAME.get(name)
    return tool.source if tool else "compute"


def tool_is_evidence(name: str) -> bool:
    tool = _BY_NAME.get(name)
    return bool(tool and tool.evidence)


__all__ = [
    "ALL_TOOLS",
    "SOURCE_LABELS",
    "TOOL_SOURCES",
    "Tool",
    "ToolContext",
    "ToolResult",
    "get_tool",
    "tool_schemas",
    "tool_source",
    "tool_is_evidence",
]
