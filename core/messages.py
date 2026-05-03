"""Message types — the shape of every entry in conversation history.

Mirrors the OpenAI chat-completions wire format because that's what
llama-server speaks. Keeping the shape close to the wire makes the
trace tab honest about what the model actually sees.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A single tool call emitted by the assistant."""
    id: str
    type: Literal["function"] = "function"
    function: dict[str, Any]  # {"name": str, "arguments": str (JSON)}

    @property
    def name(self) -> str:
        return self.function["name"]

    @property
    def arguments(self) -> str:
        # Always a JSON string per OpenAI spec; the loop parses it.
        return self.function.get("arguments", "{}")


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ToolMessage(BaseModel):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: str  # tool result, stringified


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


def to_wire(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert messages to the JSON shape llama-server expects."""
    out: list[dict[str, Any]] = []
    for m in messages:
        d = m.model_dump(exclude_none=True)
        # Assistant messages with no tool_calls drop the empty list.
        if d.get("role") == "assistant" and not d.get("tool_calls"):
            d.pop("tool_calls", None)
        out.append(d)
    return out
