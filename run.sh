#!/usr/bin/env bash
# Start the harness on port 8006 (or $PORT).
# Kills any existing process on the port first.
set -euo pipefail

PORT="${PORT:-8006}"
cd "$(dirname "$0")"

# Kill anything already on the port (best-effort).
if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
    echo "Stopping existing process on port $PORT..."
    lsof -ti tcp:"$PORT" | xargs kill -9 2>/dev/null || true
fi

if [ ! -f .env ]; then
    echo "No .env found — copying from .env.example"
    cp .env.example .env
fi

echo "Starting harness on http://localhost:$PORT"
exec uv run uvicorn main:app --port "$PORT" --reload
