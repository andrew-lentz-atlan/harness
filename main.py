"""harness — entrypoint.

Mounts:
    /api/chat        POST → SSE stream of agent events
    /api/config      GET, PUT
    /api/trace/{id}  GET, DELETE
    /                serves frontend/index.html
    /static/*        frontend/static/*
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()  # read .env before anything else touches os.environ

from api.chat import router as chat_router  # noqa: E402
from api.config import router as config_router  # noqa: E402
from api.trace import router as trace_router  # noqa: E402

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="harness", version="0.1.0")

app.include_router(chat_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(trace_router, prefix="/api")

app.mount("/static", StaticFiles(directory=FRONTEND / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
