.PHONY: install lint typecheck test demo

install:
	uv sync --extra dev

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy

test:
	uv run pytest

demo:
	./scripts/demo.sh
