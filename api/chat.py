"""POST /api/chat — runs the agent loop, streams events as SSE."""
from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.state import app_state, load_config, loop_config_from
from core.loop import run_loop
from core.messages import SystemMessage

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/chat")
async def chat(req: ChatRequest):
    cfg = load_config()
    loop_cfg = loop_config_from(cfg)
    backend = cfg.get("backend", "litellm")
    session = app_state.get_or_create(req.session_id)
    session.reset_with_system(loop_cfg.system_prompt)

    async def event_stream():
        # Send the session id first so the client can pin to it.
        yield {"event": "session", "data": json.dumps({"session_id": session.id})}

        try:
            client = app_state.client_for(backend)
        except (ValueError, RuntimeError) as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"backend init failed: {exc}"}),
            }
            return

        async for event in run_loop(
            session=session,
            user_message=req.message,
            config=loop_cfg,
            client=client,
            registry=app_state.registry,
        ):
            yield {"event": event.kind, "data": json.dumps(event.data)}

    return EventSourceResponse(event_stream())


@router.post("/chat/reset")
async def reset(session_id: str | None = None):
    """Clear a session's history."""
    if session_id and session_id in app_state.sessions:
        del app_state.sessions[session_id]
    return {"ok": True}
