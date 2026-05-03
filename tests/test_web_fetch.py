"""Tests for the web_fetch tool's pure helpers.

We don't make real HTTP calls in unit tests — that'd be slow and flaky.
We test the URL validation, HTML extraction, and SSRF guard directly.
"""
from __future__ import annotations

import pytest

from core.tools.web_fetch import (
    WebFetchTool,
    _extract_text,
    _is_internal_host,
)


# --- pure helpers ---------------------------------------------------------

def test_extract_text_strips_html():
    html = """
    <html>
      <head><title>x</title><style>body { color: red }</style></head>
      <body>
        <header>Site Header</header>
        <main>
          <h1>Hello</h1>
          <p>This is the   body  text.</p>
          <script>alert('hi')</script>
        </main>
        <footer>©</footer>
      </body>
    </html>
    """
    text = _extract_text(html)
    assert "Hello" in text
    assert "body text" in text
    assert "alert" not in text          # script removed
    assert "Site Header" not in text    # header removed
    assert "©" not in text              # footer removed
    # Whitespace was collapsed
    assert "   " not in text


def test_extract_text_collapses_blank_lines():
    html = "<div>a</div>\n\n\n\n<div>b</div>"
    text = _extract_text(html)
    # No more than one blank line between paragraphs.
    assert "\n\n\n" not in text


def test_is_internal_host_blocks_loopback():
    assert _is_internal_host("localhost") is True
    assert _is_internal_host("127.0.0.1") is True


def test_is_internal_host_blocks_private_ranges():
    assert _is_internal_host("10.0.0.1") is True
    assert _is_internal_host("192.168.1.1") is True
    assert _is_internal_host("172.16.5.5") is True


def test_is_internal_host_blocks_aws_metadata():
    # 169.254.169.254 — the AWS instance metadata service.
    assert _is_internal_host("169.254.169.254") is True


def test_is_internal_host_does_not_block_public():
    # These should resolve and be marked public. We use IP literals so
    # the test isn't sensitive to DNS.
    assert _is_internal_host("8.8.8.8") is False
    assert _is_internal_host("1.1.1.1") is False


# --- tool entry-point validation -----------------------------------------

@pytest.fixture
def tool() -> WebFetchTool:
    return WebFetchTool()


async def test_rejects_non_http_scheme(tool: WebFetchTool):
    out = await tool.run({"url": "file:///etc/passwd"})
    assert out.startswith("Error")
    assert "http/https" in out


async def test_rejects_empty_hostname(tool: WebFetchTool):
    out = await tool.run({"url": "http://"})
    assert out.startswith("Error")


async def test_rejects_loopback(tool: WebFetchTool):
    out = await tool.run({"url": "http://127.0.0.1:8080/"})
    assert out.startswith("Error")
    assert "internal/private" in out


async def test_rejects_aws_metadata(tool: WebFetchTool):
    out = await tool.run({"url": "http://169.254.169.254/latest/meta-data/"})
    assert out.startswith("Error")
    assert "internal/private" in out


async def test_invalid_args(tool: WebFetchTool):
    out = await tool.run({})  # missing url
    assert out.startswith("Error: invalid arguments")
