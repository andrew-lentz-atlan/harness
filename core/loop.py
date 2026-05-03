"""The agent loop — the heart of the harness.

This is the canonical ReAct / function-calling loop:

    while model wants to keep going:
        ask model
        if model returned tool calls:
            execute each, append results
            loop again
        else:
            return final answer

Every harness in the wild (Claude Code, smolagents, Open Interpreter)
is some variation of this. Read it once and the rest of the codebase
makes sense.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import AsyncIterator

from core.client import LlamaClient, ModelParams
from core.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from core.tools.registry import ToolRegistry
from core.trace import trace

MAX_STEPS = 10  # safety cap — without this a stuck model burns your tokens


@dataclass
class LoopConfig:
    system_prompt: str
    params: ModelParams = field(default_factory=ModelParams)
    tool_allowlist: list[str] = field(default_factory=list)
    tools_enabled: bool = True


@dataclass
class Session:
    id: str
    messages: list[Message] = field(default_factory=list)

    def reset_with_system(self, system_prompt: str) -> None:
        """Replace any existing system message with a fresh one."""
        non_system = [m for m in self.messages if not isinstance(m, SystemMessage)]
        self.messages = [SystemMessage(content=system_prompt), *non_system]


@dataclass
class LoopEvent:
    """What the API streams back to the UI."""
    kind: str           # "assistant" | "tool_call" | "tool_result" | "done" | "error"
    data: dict


async def run_loop(
    session: Session,
    user_message: str,
    config: LoopConfig,
    client: LlamaClient,
    registry: ToolRegistry,
) -> AsyncIterator[LoopEvent]:
    """Run the agent loop, yielding events as the model thinks."""
    session.messages.append(UserMessage(content=user_message))
    trace.record(session.id, "info", {"user_message": user_message})

    tools_schema = (
        registry.schemas(config.tool_allowlist)
        if config.tools_enabled and config.tool_allowlist
        else None
    )

    for step in range(MAX_STEPS):
        try:
            result = await client.complete(
                messages=session.messages,
                tools=tools_schema,
                params=config.params,
            )
        except Exception as exc:
            trace.record(session.id, "error", {"step": step, "error": str(exc)})
            yield LoopEvent("error", {"message": str(exc)})
            return

        trace.record(session.id, "request", {"step": step, "payload": result.raw_request})
        trace.record(
            session.id,
            "response",
            {
                "step": step,
                "payload": result.raw_response,
                "latency_ms": result.latency_ms,
                "usage": result.usage,
            },
        )

        session.messages.append(result.message)
        yield LoopEvent(
            "assistant",
            {
                "content": result.message.content or "",
                "tool_calls": [tc.model_dump() for tc in result.message.tool_calls],
                "latency_ms": result.latency_ms,
                "usage": result.usage,
            },
        )

        if not result.message.tool_calls:
            yield LoopEvent("done", {"step": step})
            return

        # Execute each tool call, append result, loop again.
        for call in result.message.tool_calls:
            try:
                args = json.loads(call.arguments) if call.arguments else {}
            except json.JSONDecodeError as exc:
                tool_result = f"Error: invalid JSON arguments — {exc}"
                trace.record(
                    session.id,
                    "tool_result",
                    {"step": step, "name": call.name, "error": str(exc)},
                )
            else:
                trace.record(
                    session.id,
                    "tool_call",
                    {"step": step, "name": call.name, "args": args},
                )
                yield LoopEvent("tool_call", {"name": call.name, "args": args, "id": call.id})
                tool_result = await registry.run(call.name, args)
                trace.record(
                    session.id,
                    "tool_result",
                    {"step": step, "name": call.name, "result": tool_result},
                )

            session.messages.append(
                ToolMessage(tool_call_id=call.id, content=tool_result)
            )
            yield LoopEvent("tool_result", {"id": call.id, "result": tool_result})

    # Hit the safety cap.
    trace.record(session.id, "error", {"error": f"max steps ({MAX_STEPS}) exceeded"})
    yield LoopEvent("error", {"message": f"Max steps ({MAX_STEPS}) exceeded — bailing."})
