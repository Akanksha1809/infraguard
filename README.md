# InfraGuard

Infrastructure reliability and resilience engineering platform. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md) for the
full design and build plan; this README will grow into the portfolio-facing overview at
Milestone 7.

## Status

Milestone 6 (platform integration) complete — see
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

### Simulate an infrastructure failure

```bash
uv run infraguard validate-topology --file examples/topologies/multi-zone-redundant.yaml
uv run infraguard simulate-failure \
    --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml --failure db
```

See [docs/FAILURE_SIMULATION.md](docs/FAILURE_SIMULATION.md) for the precise failure/
redundancy/capacity model and all three example topologies' results.

### Assess disaster-recovery readiness

```bash
uv run infraguard assess-recovery \
    --policy examples/recovery/policy.yaml --evidence examples/recovery/evidence.json \
    --as-of 2026-10-19T12:00:00Z
```

See [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) — the central rule is that a
backup's existence is never treated as evidence it's recoverable; six example workloads
each demonstrate one distinct readiness outcome.

### Run a real local recovery drill (optional, needs Docker)

```bash
uv run infraguard recovery-lab start
uv run infraguard recovery-lab drill --workload-id orders-db \
    --policy examples/recovery/policy.yaml --evidence-out live-evidence.json
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml --evidence live-evidence.json
uv run infraguard recovery-lab stop
```

This actually backs up, truncates, restores, and checksum-verifies a disposable Postgres
database in Docker — see docs/DISASTER_RECOVERY.md's "Local recovery lab" section for the
safety scoping and what was verified by actually running it.

### Retrieve a past run, or inspect policy

```bash
uv run infraguard runs
uv run infraguard report --run-id <id> --format markdown
uv run infraguard policy
```

Every module persists its report to one shared SQLite history (`infraguard.db` by default,
override with `--db-path`) — see [docs/POLICY_REFERENCE.md](docs/POLICY_REFERENCE.md).
