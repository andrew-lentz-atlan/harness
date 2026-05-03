"""HTTP client for llama.cpp's llama-server.

llama-server speaks the OpenAI /v1/chat/completions shape, so we just
POST JSON. We deliberately do NOT use the openai SDK — the whole point
of this harness is that you can read the wire format on the trace tab.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from core.messages import AssistantMessage, Message, ToolCall, to_wire


@dataclass
class ModelParams:
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 1024


@dataclass
class CompleteResult:
    """What the loop gets back per turn."""
    message: AssistantMessage
    raw_request: dict[str, Any]
    raw_response: dict[str, Any]
    latency_ms: int
    usage: dict[str, int]


class LlamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")).rstrip("/")
        self.model = model or os.getenv("MODEL_NAME", "local-model")
        self._http = httpx.AsyncClient(timeout=timeout)

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        params: ModelParams | None = None,
    ) -> CompleteResult:
        params = params or ModelParams()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": to_wire(messages),
            "temperature": params.temperature,
            "top_p": params.top_p,
            "max_tokens": params.max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        import time
        t0 = time.monotonic()
        resp = await self._http.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        tool_calls_raw = choice.get("tool_calls") or []
        message = AssistantMessage(
            content=choice.get("content"),
            tool_calls=[ToolCall.model_validate(tc) for tc in tool_calls_raw],
        )
        usage = data.get("usage") or {}

        return CompleteResult(
            message=message,
            raw_request=payload,
            raw_response=data,
            latency_ms=latency_ms,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()
