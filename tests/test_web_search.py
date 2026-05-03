"""Tests for the web_search tool.

The DuckDuckGo backend is mocked out so the test suite never hits the
network. We're validating: arg validation, result formatting, error
handling, and the injection-aware delimiter.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from core.tools.web_search import (
    MAX_SNIPPET_CHARS,
    WebSearchTool,
    _format_results,
)


# --- pure helpers ---------------------------------------------------------

def test_format_results_includes_title_url_snippet():
    rows = [
        {"title": "Example", "href": "https://example.com", "body": "About this."},
        {"title": "Two", "href": "https://two.example", "body": "Other thing."},
    ]
    out = _format_results(rows)
    assert "1. Example" in out
    assert "https://example.com" in out
    assert "About this." in out
    assert "2. Two" in out


def test_format_results_truncates_long_snippets():
    long_body = "x" * (MAX_SNIPPET_CHARS + 200)
    rows = [{"title": "t", "href": "u", "body": long_body}]
    out = _format_results(rows)
    assert len(out) < len(long_body) + 200
    assert "…" in out  # ellipsis marker


def test_format_results_handles_missing_fields():
    rows = [{"title": None, "href": None, "body": None}]
    # Shouldn't crash on missing fields.
    _format_results(rows)


# --- tool entry-point ----------------------------------------------------

@pytest.fixture
def tool() -> WebSearchTool:
    return WebSearchTool()


async def test_invalid_args(tool: WebSearchTool):
    out = await tool.run({})  # missing query
    assert out.startswith("Error: invalid arguments")


async def test_num_results_clamped_to_max(tool: WebSearchTool):
    # Pydantic should reject too-large num_results before we even call ddgs.
    out = await tool.run({"query": "x", "num_results": 999})
    assert out.startswith("Error: invalid arguments")


async def test_returns_formatted_results(tool: WebSearchTool):
    fake = [
        {"title": "Hi", "href": "https://hi.example", "body": "snippet"},
    ]
    with patch("core.tools.web_search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = fake
        out = await tool.run({"query": "anything"})

    assert "<web_search_results" in out
    assert 'query="anything"' in out
    assert 'count="1"' in out
    assert "Hi" in out
    assert "https://hi.example" in out
    assert out.rstrip().endswith("</web_search_results>")


async def test_no_results_returns_friendly_message(tool: WebSearchTool):
    with patch("core.tools.web_search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.return_value = []
        out = await tool.run({"query": "asdfqwerty"})
    assert "No results" in out
    assert "asdfqwerty" in out


async def test_backend_exception_is_returned_as_error(tool: WebSearchTool):
    with patch("core.tools.web_search.DDGS") as MockDDGS:
        MockDDGS.return_value.text.side_effect = RuntimeError("rate limit")
        out = await tool.run({"query": "anything"})
    assert out.startswith("Error: web_search failed")
    assert "rate limit" in out
