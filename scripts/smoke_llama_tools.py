"""Day-zero smoke test: does this llama-server emit OpenAI-shape tool_calls?

Run this BEFORE building anything else. If it passes, the tool-calling path
in the harness will work. If it fails, we know we need a fallback parser
(XML tags) and we know it now, not after wiring the full UI.

Usage:
    make smoke
or:
    uv run python -m scripts.smoke_llama_tools
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8080").rstrip("/")
MODEL = os.getenv("MODEL_NAME", "local-model")

PAYLOAD = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "You can call tools. Use them when helpful."},
        {"role": "user", "content": "What's the weather in Tokyo? Use the get_weather tool."},
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name."},
                    },
                    "required": ["city"],
                },
            },
        }
    ],
    "tool_choice": "auto",
    "max_tokens": 256,
}


async def main() -> int:
    print(f"POST {URL}/v1/chat/completions ...")
    async with httpx.AsyncClient(timeout=60) as http:
        try:
            resp = await http.post(f"{URL}/v1/chat/completions", json=PAYLOAD)
        except httpx.HTTPError as exc:
            print(f"FAIL: could not reach llama-server: {exc}")
            print("Hint: start llama-server with --jinja, e.g.")
            print("  llama-server -m gemma-3-4b-it-q4_k_m.gguf -c 8192 --jinja --port 8080")
            return 2

    if resp.status_code != 200:
        print(f"FAIL: HTTP {resp.status_code}")
        print(resp.text[:500])
        return 2

    data = resp.json()
    msg = data["choices"][0]["message"]
    print("\n--- assistant message ---")
    print(json.dumps(msg, indent=2)[:1200])

    if msg.get("tool_calls"):
        print(f"\nPASS: server returned {len(msg['tool_calls'])} tool_call(s).")
        return 0

    print("\nWARN: no tool_calls field in the response.")
    print("Possible reasons: server started without --jinja, model doesn't")
    print("emit OpenAI-shape tool calls, or the prompt didn't trigger one.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
