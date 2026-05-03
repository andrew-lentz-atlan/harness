"""read_file — the v1 tool. Reads a file from the harness sandbox.

The sandbox check is the harness's first guardrail. Without it, a model
can hallucinate `/etc/passwd` and we hand it over. With it, the worst
case is the model reads its own sandbox.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from core.tools.base import Tool


SANDBOX_DIR = Path(__file__).resolve().parents[2] / "sandbox"
MAX_BYTES = 100_000  # cap so a huge file doesn't blow the context window


class ReadFileArgs(BaseModel):
    path: str = Field(
        ...,
        description="Path to a file inside the sandbox, relative to the sandbox root.",
    )


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a text file from the harness sandbox. "
        "Returns the file's text. Paths are relative to the sandbox root; "
        "absolute paths and parent traversal (..) are rejected."
    )
    args_schema = ReadFileArgs

    def __init__(self, sandbox: Path = SANDBOX_DIR):
        self.sandbox = sandbox.resolve()
        self.sandbox.mkdir(parents=True, exist_ok=True)

    async def run(self, args: dict[str, Any]) -> str:
        try:
            parsed = ReadFileArgs.model_validate(args)
        except Exception as exc:
            return f"Error: invalid arguments — {exc}"

        target = (self.sandbox / parsed.path).resolve()

        # The guardrail. Reject anything outside the sandbox.
        try:
            target.relative_to(self.sandbox)
        except ValueError:
            return (
                f"Error: '{parsed.path}' is outside the sandbox. "
                f"Only paths under {self.sandbox.name}/ are allowed."
            )

        if not target.exists():
            return f"Error: file not found — {parsed.path}"
        if not target.is_file():
            return f"Error: not a file — {parsed.path}"

        try:
            data = target.read_bytes()
        except OSError as exc:
            return f"Error reading file: {exc}"

        truncated = ""
        if len(data) > MAX_BYTES:
            data = data[:MAX_BYTES]
            truncated = f"\n\n[truncated at {MAX_BYTES} bytes]"

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return f"Error: '{parsed.path}' is not UTF-8 text."

        return text + truncated
