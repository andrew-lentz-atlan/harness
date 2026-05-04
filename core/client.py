"""HTTP clients to OpenAI-compatible chat-completions endpoints.

Two backends, both speaking the same `/v1/chat/completions` wire format:

- `LlamaServerClient` — a local llama.cpp llama-server (no auth required).
- `LiteLLMClient` — a hosted OpenAI-compatible proxy (Atlan's LiteLLM
  proxy or any equivalent), authenticated with a Bearer token.

We deliberately do NOT use the openai SDK. The whole point of this
harness is that the wire format stays visible — the trace tab shows the
exact JSON we send and receive.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
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
    """What the agent loop gets back per turn."""
    message: AssistantMessage
    raw_request: dict[str, Any]
    raw_response: dict[str, Any]
    latency_ms: int
    usage: dict[str, int]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ModelClient(ABC):
    """A chat-completions client. Both implementations POST OpenAI-shaped
    JSON to `/v1/chat/completions`. They differ in URL, default port, and
    auth headers — the request/response handling is shared.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        params: ModelParams | None = None,
    ) -> CompleteResult: ...

    @abstractmethod
    async def aclose(self) -> None: ...


# ---------------------------------------------------------------------------
# Shared base — OpenAI-compatible HTTP
# ---------------------------------------------------------------------------

class _OpenAICompatClient(ModelClient):
    """Shared logic for any OpenAI-compatible chat-completions endpoint."""

    # Subclasses can declare payload keys that this backend's downstream
    # provider doesn't accept. They get stripped before the POST. Used to
    # paper over cross-provider quirks (e.g. Bedrock's Claude routes
    # reject top_p when temperature is also set).
    excluded_payload_keys: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
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
        for key in self.excluded_payload_keys:
            payload.pop(key, None)

        t0 = time.monotonic()
        resp = await self._http.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=self._headers,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Surface the response body on errors so 400s from the proxy
        # name the actual problem field instead of just "Bad Request".
        if resp.status_code >= 400:
            body = resp.text[:2000] if resp.text else "(empty body)"
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code} from {self.base_url}\n"
                f"Response body: {body}\n"
                f"Request payload (truncated): {str(payload)[:500]}",
                request=resp.request,
                response=resp,
            )
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


# ---------------------------------------------------------------------------
# Concrete backends
# ---------------------------------------------------------------------------

class LlamaServerClient(_OpenAICompatClient):
    """Talks to a local llama.cpp `llama-server`. No auth.

    Env vars (or kwargs):
        LLAMA_SERVER_URL    default: http://localhost:8080
        MODEL_NAME          default: local-model (llama-server ignores this
                                                   and serves whatever was
                                                   loaded with -m)
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(
            base_url=base_url or os.getenv("LLAMA_SERVER_URL", "http://localhost:8080"),
            api_key=None,
            model=model or os.getenv("MODEL_NAME", "local-model"),
            timeout=timeout,
        )


class LiteLLMClient(_OpenAICompatClient):
    """Talks to an OpenAI-compatible hosted proxy (Atlan's LiteLLM proxy
    or any equivalent that exposes `/v1/chat/completions`).

    Env vars (or kwargs):
        LITELLM_BASE_URL    proxy URL (REQUIRED)
        LITELLM_API_KEY     auth key (REQUIRED) — sent as `Bearer <key>`
        MODEL_NAME          default: claude-haiku-4-5

    Why we strip top_p:
        Atlan's LiteLLM proxy routes Claude models through Bedrock, and
        Bedrock's Claude implementation rejects requests that set both
        `temperature` and `top_p` ("cannot both be specified for this
        model"). Anthropic's native API accepts both; the translation
        layer doesn't. We default to keeping `temperature` and dropping
        `top_p`. If a future model needs top_p instead, override this
        list per-instance or refactor to a model-aware policy.
    """
    excluded_payload_keys = ("top_p",)

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        url = base_url or os.getenv("LITELLM_BASE_URL", "").strip()
        key = api_key or os.getenv("LITELLM_API_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "LITELLM_BASE_URL and LITELLM_API_KEY must be set "
                "(in your shell or in harness/.env). See .env.example."
            )
        super().__init__(
            base_url=url,
            api_key=key,
            model=model or os.getenv("MODEL_NAME", "claude-haiku-4-5"),
            timeout=timeout,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

AVAILABLE_BACKENDS = ("litellm", "llama-server")


def make_client(backend: str = "litellm", **kwargs: Any) -> ModelClient:
    """Pick a backend by name. `backend` defaults to litellm so a fresh
    clone with proxy creds works immediately; pass 'llama-server' to use
    a local model instead.
    """
    if backend == "llama-server":
        return LlamaServerClient(**kwargs)
    if backend == "litellm":
        return LiteLLMClient(**kwargs)
    raise ValueError(
        f"Unknown backend {backend!r}. Available: {AVAILABLE_BACKENDS}."
    )


# Backwards-compat alias — anything that imports LlamaClient gets the
# same behavior as before. Will be removed once nothing references it.
LlamaClient = LlamaServerClient
