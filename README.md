# harness

A minimal LLM agent harness, built from scratch to learn what goes inside one.

The "brain" is a local model running under [`llama-server`](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) (llama.cpp's OpenAI-compatible HTTP server). The harness is a thin Python layer that runs the agent loop, exposes a chat UI, and lets you tweak its behavior live.

## What's here

- A canonical agent loop (`core/loop.py`) — you can read it in one sitting
- An OpenAI-shaped HTTP client to `llama-server` (`core/client.py`) — no SDK, the wire format stays visible
- Three sandboxed tools (`core/tools/`):
  - `read_file` — reads from a sandboxed directory
  - `web_fetch` — fetches a URL with SSRF + injection guards
  - `web_search` — DuckDuckGo search
- A web UI with: chat panel, sidebar config (system prompt, temperature, reasoning-style preset, tool allowlist), and a **Trace tab** that shows every message the model sees
- File-backed config (`config/default.yaml`) — no DB, no migrations
- 32 unit tests covering the loop, the tools, and their guardrails

## Run it

```bash
# 1. Start a llama-server somewhere with a Gemma (or compatible) model
llama-server -hf unsloth/gemma-4-E4B-it-GGUF:Q4_K_M -c 8192 --jinja --port 8080

# 2. From this directory
cp .env.example .env       # point at the llama-server
uv sync                    # install deps
./run.sh                   # serves http://localhost:8006
```

Then open http://localhost:8006.

## Why these choices

This is a learning project. Every piece is chosen to be readable, not production-grade.

- **No openai SDK** — `httpx` directly, so the JSON wire format is right there.
- **No build step on the frontend** — vanilla HTML + JS. Open `frontend/index.html` and you can read the whole client.
- **No DB** — YAML for config, JSON for sessions. `cat` works.
- **Sandboxed tools** — `read_file` is locked to `./sandbox/`; `web_fetch` rejects loopback, private, and AWS-metadata IPs. Standard guardrails, written explicitly.
- **Full trace visibility** — the Trace tab shows every request and response byte the model sees. The OOTB harnesses (Claude Code, Cursor) summarize traces because their cost incentives don't reward full visibility. This one's incentives are different.

## Status / Roadmap

**Currently:** llama-server backend only. To run it, you need a local model running.

**Imminent next step:** Hosted-model backend support via LiteLLM proxy (so you can point this at a managed `claude-haiku-4-5`, `gpt-4o`, etc. without a local model). The plan is to refactor `core/client.py` into a `ModelClient` interface with two implementations — `LlamaServerClient` and `LiteLLMClient` — and add a `backend` field to the config. This is what makes the harness usable by anyone with proxy creds, not just folks with `llama-server` running locally.

**Beyond that:**
- More tools (`write_file`, `bash`, custom tool hot-reload)
- Memory: short-term compaction + persistent memory (Claude Code-style markdown files)
- Module swap UI (multiple reasoners, memory backends, plug-in tools)

## Used by

- [discovery-inception](https://github.com/andrew-lentz-atlan/discovery-inception) — a research project on chained-agent discovery for AI use cases. The harness is the runtime that consumes the discovery system's `RoleContext` outputs and runs the agent, and its trace view is the introspection layer that closes the discovery → build → trace → feedback loop.
