.PHONY: dev test smoke install clean

PORT ?= 8006

install:
	uv sync

dev:
	uv run uvicorn main:app --port $(PORT) --reload

test:
	uv run pytest -q

smoke:
	@echo "Smoke-testing llama-server tool calling..."
	@uv run python -m scripts.smoke_llama_tools

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
