"""Per-session trace log.

The Trace tab is the most important learning surface in v1: it shows
exactly what the model saw and said on every turn. Trace events are
kept in memory only — by design — so you can `cat` nothing and reason
about everything in one place.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from typing import Any

MAX_EVENTS_PER_SESSION = 500


class TraceEvent:
    def __init__(self, kind: str, payload: dict[str, Any]):
        self.id = uuid.uuid4().hex[:8]
        self.ts = time.time()
        self.kind = kind         # "request" | "response" | "tool_call" | "tool_result" | "info" | "error"
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "kind": self.kind,
            "payload": self.payload,
        }


class TraceLog:
    def __init__(self) -> None:
        self._sessions: dict[str, deque[TraceEvent]] = defaultdict(
            lambda: deque(maxlen=MAX_EVENTS_PER_SESSION)
        )

    def record(self, session_id: str, kind: str, payload: dict[str, Any]) -> TraceEvent:
        event = TraceEvent(kind, payload)
        self._sessions[session_id].append(event)
        return event

    def get(self, session_id: str) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._sessions.get(session_id, ())]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


trace = TraceLog()
