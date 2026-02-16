.PHONY: sync test lint fmt

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
