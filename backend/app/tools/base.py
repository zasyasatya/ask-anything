"""Tool primitives: JSON-schema tools + sandboxed executors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..config import Settings


@dataclass
class ToolContext:
    settings: Settings
    http: Any = None  # httpx.AsyncClient, injected for testability


@dataclass
class ToolResult:
    summary: str                    # short human-readable line for the trace
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]      # JSON schema
    run: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
