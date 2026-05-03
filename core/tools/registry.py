"""Tool registry — register, list, schema-export, run."""
from __future__ import annotations

from typing import Any

from core.tools.base import Tool
from core.tools.read_file import ReadFileTool
from core.tools.web_fetch import WebFetchTool
from core.tools.web_search import WebSearchTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self, allowlist: list[str] | None = None) -> list[dict[str, Any]]:
        """OpenAI-format schemas for the `tools=` field. Filtered by allowlist."""
        names = allowlist if allowlist is not None else self.names()
        return [
            self._tools[n].openai_schema()
            for n in names
            if n in self._tools
        ]

    async def run(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'. Known tools: {', '.join(self.names()) or 'none'}."
        try:
            return await tool.run(args)
        except Exception as exc:
            return f"Error executing {name}: {exc}"


def _make_default_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(ReadFileTool())
    r.register(WebFetchTool())
    r.register(WebSearchTool())
    return r


default_registry = _make_default_registry()
