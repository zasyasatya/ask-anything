"""Provider abstraction: every LLM backend yields a normalised event stream.

Event types (StreamEvent.type):
  thinking   — model reasoning text delta (chain-of-thought)
  delta      — answer text delta
  logprobs   — token-level probability info (mechanistic interpreter)
  tool_calls — list of ToolCall the model wants to execute
  usage      — token/latency accounting
  error      — provider failure
  done       — end of one provider turn
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class StreamEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class BaseProvider:
    name = "base"

    def model_label(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        logprobs: bool = False,
        top_logprobs: int = 4,
    ) -> AsyncIterator[StreamEvent]:  # pragma: no cover - overridden
        raise NotImplementedError
        # yield  # unreachable; makes this an async generator signature
