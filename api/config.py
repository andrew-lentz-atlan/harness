"""GET/PUT /api/config — round-trip the YAML config from disk."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import list_presets, load_config, save_config
from core.tools.registry import default_registry

router = APIRouter()


class ConfigPayload(BaseModel):
    config: dict[str, Any]


@router.get("/config")
def get_config():
    return {
        "config": load_config(),
        "presets": list_presets(),
        "available_tools": default_registry.names(),
    }


@router.put("/config")
def put_config(payload: ConfigPayload):
    cfg = payload.config
    if not isinstance(cfg, dict):
        raise HTTPException(400, "config must be an object")
    if "system_prompt" not in cfg:
        raise HTTPException(400, "config.system_prompt is required")
    save_config(cfg)
    return {"ok": True, "config": load_config()}
