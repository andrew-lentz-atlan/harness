"""Tool base class. Subclass, declare an args schema, implement run()."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]

    @abstractmethod
    async def run(self, args: dict[str, Any]) -> str:
        """Execute the tool. Always return a string — that's what the model sees."""

    def openai_schema(self) -> dict[str, Any]:
        """Render this tool in the OpenAI function-calling shape."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }
