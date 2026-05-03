"""Loop tests with a fake client. Asserts the loop terminates correctly."""
from __future__ import annotations

import json
from typing import Any

import pytest

from core.client import CompleteResult, ModelParams
from core.loop import LoopConfig, MAX_STEPS, Session, run_loop
from core.messages import AssistantMessage, ToolCall
from core.tools.base import Tool
from core.tools.registry import ToolRegistry
from pydantic import BaseModel


# --- fake tool -------------------------------------------------------------

class _EchoArgs(BaseModel):
    text: str


class _EchoTool(Tool):
    name = "echo"
    description = "Echoes the input."
    args_schema = _EchoArgs

    async def run(self, args: dict[str, Any]) -> str:
        return f"echo: {args.get('text', '')}"


# --- fake client -----------------------------------------------------------

class _FakeClient:
    """Returns canned CompleteResults in order."""

    def __init__(self, responses: list[AssistantMessage]):
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages, tools=None, params=None):
        self.calls += 1
        msg = self._responses.pop(0)
        return CompleteResult(
            message=msg,
            raw_request={"messages": [], "tools": tools},
            raw_response={"choices": [{"message": msg.model_dump()}]},
            latency_ms=1,
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )


def _registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(_EchoTool())
    return r


def _config() -> LoopConfig:
    return LoopConfig(
        system_prompt="you are a test",
        params=ModelParams(),
        tool_allowlist=["echo"],
        tools_enabled=True,
    )


# --- tests -----------------------------------------------------------------

async def test_loop_terminates_with_no_tool_calls():
    client = _FakeClient([AssistantMessage(content="hi back")])
    session = Session(id="s1")
    events = []
    async for ev in run_loop(session, "hello", _config(), client, _registry()):
        events.append(ev)

    kinds = [e.kind for e in events]
    assert "assistant" in kinds
    assert kinds[-1] == "done"
    assert client.calls == 1


async def test_loop_executes_one_tool_call_then_finishes():
    tool_call = ToolCall(
        id="call_1",
        function={"name": "echo", "arguments": json.dumps({"text": "hi"})},
    )
    client = _FakeClient([
        AssistantMessage(content=None, tool_calls=[tool_call]),
        AssistantMessage(content="all done"),
    ])
    session = Session(id="s2")
    events = []
    async for ev in run_loop(session, "do it", _config(), client, _registry()):
        events.append(ev)

    kinds = [e.kind for e in events]
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert kinds[-1] == "done"
    assert client.calls == 2

    # The tool result should have been appended to session messages.
    assert any(m.role == "tool" for m in session.messages)
    tool_msg = next(m for m in session.messages if m.role == "tool")
    assert tool_msg.content == "echo: hi"


async def test_loop_handles_invalid_tool_json_arguments():
    bad_call = ToolCall(
        id="call_bad",
        function={"name": "echo", "arguments": "not-json"},
    )
    client = _FakeClient([
        AssistantMessage(content=None, tool_calls=[bad_call]),
        AssistantMessage(content="recovered"),
    ])
    session = Session(id="s3")
    events = [ev async for ev in run_loop(session, "x", _config(), client, _registry())]

    # Should still complete — bad-json error is fed back to the model as a tool result.
    assert events[-1].kind == "done"
    tool_msg = next(m for m in session.messages if m.role == "tool")
    assert "Error: invalid JSON" in tool_msg.content


async def test_loop_hits_max_steps_safety_cap():
    # Always return a tool call → loop spins forever without the cap.
    forever = AssistantMessage(
        content=None,
        tool_calls=[ToolCall(id="x", function={"name": "echo", "arguments": "{}"})],
    )
    client = _FakeClient([forever] * (MAX_STEPS + 5))
    session = Session(id="s4")
    events = [ev async for ev in run_loop(session, "spin", _config(), client, _registry())]

    assert events[-1].kind == "error"
    assert "Max steps" in events[-1].data["message"]
    assert client.calls == MAX_STEPS


async def test_loop_runs_with_no_tools_when_disabled():
    cfg = _config()
    cfg.tools_enabled = False
    client = _FakeClient([AssistantMessage(content="no tools needed")])
    session = Session(id="s5")
    events = [ev async for ev in run_loop(session, "hi", cfg, client, _registry())]
    assert events[-1].kind == "done"


async def test_unknown_tool_returns_error_to_model():
    bad_call = ToolCall(
        id="c", function={"name": "no_such_tool", "arguments": "{}"},
    )
    client = _FakeClient([
        AssistantMessage(content=None, tool_calls=[bad_call]),
        AssistantMessage(content="ok"),
    ])
    session = Session(id="s6")
    events = [ev async for ev in run_loop(session, "x", _config(), client, _registry())]

    assert events[-1].kind == "done"
    tool_msg = next(m for m in session.messages if m.role == "tool")
    assert "unknown tool" in tool_msg.content
