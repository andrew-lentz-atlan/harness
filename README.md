# harness

A minimal LLM agent harness, built from scratch to learn what goes inside one.

The "brain" can be either a local model (via [`llama-server`](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) — llama.cpp's OpenAI-compatible HTTP server) or any hosted OpenAI-compatible proxy (Atlan's LiteLLM proxy, etc.). Pick the backend in the sidebar; switch any time.

## What's here

- A canonical agent loop ([`core/loop.py`](core/loop.py)) — you can read it in one sitting
- A `ModelClient` interface ([`core/client.py`](core/client.py)) with two backends:
  - `LlamaServerClient` — local llama.cpp, no auth
  - `LiteLLMClient` — hosted OpenAI-compatible proxy, Bearer auth
- Three sandboxed tools (`core/tools/`):
  - `read_file` — reads from a sandboxed directory
  - `web_fetch` — fetches a URL with SSRF + injection guards
  - `web_search` — DuckDuckGo search
- A web UI: chat panel, sidebar config (backend, system prompt, model params, reasoning-style preset, tool allowlist), and a **Trace tab** that shows every message the model sees
- File-backed config (`config/default.yaml`) — no DB, no migrations
- 32 unit tests covering the loop, the tools, and their guardrails

## Run it

### Option A — hosted proxy (default)

If you have an OpenAI-compatible proxy (e.g. Atlan's LiteLLM proxy):

```bash
cp .env.example .env       # fill in LITELLM_BASE_URL + LITELLM_API_KEY
uv sync                    # install deps
./run.sh                   # serves http://localhost:8006
```

The default config uses `claude-haiku-4-5`; change `model.name` in the sidebar to anything your proxy serves.

### Option B — local llama-server

If you'd rather run the model on your own laptop:

```bash
# In one terminal, start the model server:
llama-server -hf unsloth/gemma-4-E4B-it-GGUF:Q4_K_M -c 8192 --jinja --port 8080

# In another:
cp .env.example .env       # LLAMA_SERVER_URL is preconfigured
uv sync
./run.sh
```

Then in the sidebar, switch **Backend** from `litellm` to `llama-server` and Save.

Open http://localhost:8006.

## Why these choices

This is a learning project. Every piece is chosen to be readable, not production-grade.

- **No openai SDK** — `httpx` directly, so the JSON wire format is right there.
- **No build step on the frontend** — vanilla HTML + JS. Open `frontend/index.html` and you can read the whole client.
- **No DB** — YAML for config, JSON for sessions. `cat` works.
- **Sandboxed tools** — `read_file` is locked to `./sandbox/`; `web_fetch` rejects loopback, private, and AWS-metadata IPs. Standard guardrails, written explicitly.
- **Full trace visibility** — the Trace tab shows every request and response byte the model sees. The OOTB harnesses (Claude Code, Cursor) summarize traces because their cost incentives don't reward full visibility. This one's incentives are different.
- **Backend swap, not lock-in** — same `ModelClient` interface, two implementations. Same code path runs against a local Gemma or a hosted Claude. Pick per task.

## Roadmap

- [x] **Phase 1** — chat loop, tools, trace UI
- [x] **Phase 2** — more tools (web_fetch, web_search), guardrails, tests
- [x] **Phase 2c** — LiteLLM backend (this commit) — usable with hosted models, no local install required
- [ ] **Phase 3** — short-term context compaction + persistent memory (Claude Code-style markdown files)
- [ ] **Phase 4** — module swap UI (multiple reasoners, memory backends, plug-in tools), per-stage backend selection (cheap model for simple steps, frontier model for hard ones)

## Used by

- [discovery-inception](https://github.com/andrew-lentz-atlan/discovery-inception) — a research project on chained-agent discovery for AI use cases. The harness is the runtime that consumes the discovery system's `RoleContext` outputs and runs the agent, and its trace view is the introspection layer that closes the discovery → build → trace → feedback loop.
