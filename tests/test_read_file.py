"""Sandbox guardrail tests for the read_file tool."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.tools.read_file import ReadFileTool


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    sb = tmp_path / "sandbox"
    sb.mkdir()
    (sb / "hello.txt").write_text("hi from sandbox")
    sub = sb / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested content")
    return sb


@pytest.fixture
def tool(sandbox: Path) -> ReadFileTool:
    return ReadFileTool(sandbox=sandbox)


async def test_reads_file_inside_sandbox(tool: ReadFileTool):
    assert await tool.run({"path": "hello.txt"}) == "hi from sandbox"


async def test_reads_nested_file(tool: ReadFileTool):
    assert await tool.run({"path": "sub/nested.txt"}) == "nested content"


async def test_rejects_absolute_path(tool: ReadFileTool):
    result = await tool.run({"path": "/etc/passwd"})
    assert result.startswith("Error")
    assert "outside the sandbox" in result


async def test_rejects_parent_traversal(tool: ReadFileTool, sandbox: Path):
    # Create a sibling file outside the sandbox.
    outside = sandbox.parent / "outside.txt"
    outside.write_text("secret")
    result = await tool.run({"path": "../outside.txt"})
    assert result.startswith("Error")
    assert "outside the sandbox" in result


async def test_missing_file(tool: ReadFileTool):
    result = await tool.run({"path": "nope.txt"})
    assert "not found" in result


async def test_rejects_directory(tool: ReadFileTool):
    result = await tool.run({"path": "sub"})
    assert "not a file" in result


async def test_invalid_args(tool: ReadFileTool):
    result = await tool.run({})  # missing path
    assert result.startswith("Error: invalid arguments")
