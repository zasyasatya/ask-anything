"""Tool primitives: JSON-schema tools + sandboxed executors.

Every tool declares its **provenance** (`source`) so the UI can tell the user
where a piece of output came from:

  browser  — external evidence fetched from the web (`web_search`, `fetch_url`).
             Its results must be cited; when it returns nothing the UI says so
             explicitly instead of showing an empty bubble.
  diagram  — generated content (`create_diagram`). NOT external evidence: the
             shape comes from the model, only the renderer is deterministic.
  compute  — deterministic local computation (`calculator`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..config import Settings

#: Provenance classes shown as badges in the chat and the interpreter.
TOOL_SOURCES = ("browser", "diagram", "compute")

#: Human-readable badge labels (kept short; the UI owns the actual styling).
SOURCE_LABELS: dict[str, str] = {
    "browser": "Browser",
    "diagram": "Tool diagram",
    "compute": "Kalkulator",
}


@dataclass
class ToolContext:
    settings: Settings
    http: Any = None  # httpx.AsyncClient, injected for testability
    #: Asal run — dipakai tool generatif untuk melabeli artifact-nya.
    conversation_id: str = ""
    run_id: str = ""


@dataclass
class ToolResult:
    summary: str                    # short human-readable line for the trace
    data: dict[str, Any] = field(default_factory=dict)
    #: False for a handled failure (network error, bad argument, …).
    ok: bool = True
    #: Number of external evidence items produced (browser tools); None for
    #: tools that never yield sources — lets the UI say "0 hasil" vs "n/a".
    hits: int | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]      # JSON schema
    run: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    #: Where the output comes from — see TOOL_SOURCES.
    source: str = "compute"
    #: True when the payload is external evidence that must be cited.
    evidence: bool = False

    @property
    def label(self) -> str:
        """Short badge label for the UI."""
        return SOURCE_LABELS.get(self.source, self.name)

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
