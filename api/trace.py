"""GET /api/trace/{session_id} — the trace tab data."""
from fastapi import APIRouter

from core.trace import trace

router = APIRouter()


@router.get("/trace/{session_id}")
def get_trace(session_id: str):
    return {"session_id": session_id, "events": trace.get(session_id)}


@router.delete("/trace/{session_id}")
def clear_trace(session_id: str):
    trace.clear(session_id)
    return {"ok": True}
