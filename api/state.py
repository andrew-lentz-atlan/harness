"""Process-wide app state: client, registry, sessions, config."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml

from core.client import LlamaClient, ModelParams
from core.loop import LoopConfig, Session
from core.tools.registry import default_registry

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "default.yaml"
PRESETS_DIR = ROOT / "config" / "presets"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


def save_config(cfg: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def list_presets() -> list[dict[str, Any]]:
    if not PRESETS_DIR.exists():
        return []
    out = []
    for p in sorted(PRESETS_DIR.glob("*.yaml")):
        with p.open() as f:
            data = yaml.safe_load(f) or {}
        out.append({"id": p.stem, **data})
    return out


def load_preset(preset_id: str) -> dict[str, Any] | None:
    p = PRESETS_DIR / f"{preset_id}.yaml"
    if not p.exists():
        return None
    with p.open() as f:
        return yaml.safe_load(f) or {}


def loop_config_from(cfg: dict[str, Any]) -> LoopConfig:
    """Resolve a YAML config (with possible reasoning_style preset) into a LoopConfig."""
    system_prompt = cfg.get("system_prompt", "")
    style = cfg.get("reasoning_style", "default")
    if style and style != "default":
        preset = load_preset(style)
        if preset and preset.get("system_prompt"):
            # Append the style instruction so the user's base prompt still wins on identity.
            system_prompt = f"{system_prompt}\n\n{preset['system_prompt']}".strip()

    model = cfg.get("model", {})
    params = ModelParams(
        temperature=float(model.get("temperature", 0.7)),
        top_p=float(model.get("top_p", 0.95)),
        max_tokens=int(model.get("max_tokens", 1024)),
    )
    tools_cfg = cfg.get("tools", {}) or {}
    return LoopConfig(
        system_prompt=system_prompt,
        params=params,
        tool_allowlist=list(tools_cfg.get("allowlist", [])),
        tools_enabled=bool(tools_cfg.get("enabled", True)),
    )


class AppState:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.registry = default_registry
        self.client = LlamaClient()

    def get_or_create(self, session_id: str | None) -> Session:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        sid = session_id or uuid.uuid4().hex[:12]
        sess = Session(id=sid)
        self.sessions[sid] = sess
        return sess


app_state = AppState()
