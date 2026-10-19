# InfraGuard

Infrastructure reliability and resilience engineering platform. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md) for the
full design and build plan; this README will grow into the portfolio-facing overview at
Milestone 7.

## Status

Milestone 1 (project foundation) in progress — see
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for exactly what works today.

## Quickstart (current)

```bash
uv sync --extra dev
uv run pytest
uv run infraguard --help
uv run infraguard serve --reload
# or directly:
uv run uvicorn infraguard.api.app:create_app --factory --reload
```
