.PHONY: install lint test demo

install:
	uv sync --extra dev

lint:
	uv run ruff check src tests

test:
	uv run pytest

demo:
	@echo "The scripted demo lands in Milestone 7 (see docs/ROADMAP.md)."
	@echo "For now: make install && make test, or uv run infraguard --help"
