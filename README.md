# InfraGuard

Infrastructure reliability and resilience engineering platform. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md) for the
full design and build plan; this README will grow into the portfolio-facing overview at
Milestone 7.

## Status

Milestone 2 (Terraform Change Impact Analyzer) complete — see
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for exactly what works today
and [docs/ROADMAP.md](docs/ROADMAP.md) for what's next.

## Quickstart (current)

```bash
uv sync --extra dev
uv run pytest
uv run infraguard --help
uv run infraguard serve --reload
# or directly:
uv run uvicorn infraguard.api.app:create_app --factory --reload
```

### Analyze a Terraform plan for change risk

```bash
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json
```

See [docs/CHANGE_ANALYSIS.md](docs/CHANGE_ANALYSIS.md) for the full workflow (including how
that example `plan.json` was generated), the risk rules, and the policy/exit-code reference.
