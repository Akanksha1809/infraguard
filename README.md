# InfraGuard

Infrastructure reliability and resilience engineering platform. Runs entirely on your own
machine: no cloud account, no paid API, no credentials, no network access required for any
mandatory functionality.

## The problem

Before a risky infrastructure change, an SRE or platform engineer actually wants three
questions answered — and most tooling answers at most one of them:

1. **Can this change introduce risk?** — Terraform plans get applied based on a diff that's
   often skimmed, not analyzed.
2. **What happens if part of the infrastructure fails?** — redundancy is usually assumed,
   not verified against the actual dependency graph.
3. **Can the infrastructure actually recover?** — "we have backups" is routinely mistaken
   for "we can recover," and the two are not the same claim.

InfraGuard answers all three, locally, with one consistent reporting format, and it says so
plainly whenever it can't answer confidently rather than guessing.

## Features

- **Terraform change impact analysis** — parses `terraform show -json` plan output,
  builds a dependency graph, redacts secrets, and applies deterministic risk rules with a
  configurable CI policy (fail/warn/pass, never an unexplained numeric score). →
  [docs/CHANGE_ANALYSIS.md](docs/CHANGE_ANALYSIS.md)
- **Failure-domain simulation** — a declarative topology (components, dependencies,
  redundancy groups, failure domains), cascading-failure propagation, single-point-of-
  failure and redundancy-gap detection, and surviving-capacity math. →
  [docs/FAILURE_SIMULATION.md](docs/FAILURE_SIMULATION.md)
- **Disaster recovery readiness** — five independently-tracked dimensions (policy
  configured / backup evidence present / integrity verified / restore tested / objectives
  demonstrated by measurement), plus an optional local Docker/Postgres lab that actually
  performs a backup → data-loss → restore → verify cycle instead of only accepting
  hand-written evidence. → [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md)
- **One platform underneath all three** — shared report format (JSON + Markdown), a
  SQLite-backed run history retrievable by id through both the CLI and a FastAPI API, and
  a policy-inspection command that states plainly which thresholds are actually
  configurable. → [docs/POLICY_REFERENCE.md](docs/POLICY_REFERENCE.md)

## Architecture

A modular monolith, not microservices: one Python package, one FastAPI app, one CLI, one
SQLite database, three independent module subpackages sharing common primitives (models,
a NetworkX-backed graph helper, report rendering). Full diagram and design rationale in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the trade-offs behind specific choices (uv
over Poetry, no migration framework, `docker exec` over a local Postgres client, etc.) are
in [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md).

## Quickstart

```bash
git clone <this repo> && cd infraguard
make install   # uv sync --extra dev
make lint      # ruff
make typecheck # mypy
make test      # pytest — 209 tests, ~18s
make demo      # scripts/demo.sh — see "Demo" below
```

No step above requires Docker. The recovery lab (below) is the one optional capability that
does, and everything else explains plainly when it's unavailable rather than failing
silently.

## Usage

### Analyze a Terraform plan for change risk

```bash
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json
```

That `plan.json` is real `terraform show -json` output, not hand-written — see
[docs/CHANGE_ANALYSIS.md](docs/CHANGE_ANALYSIS.md) for the exact commands that produced it.

### Simulate an infrastructure failure

```bash
uv run infraguard validate-topology --file examples/topologies/multi-zone-redundant.yaml
uv run infraguard simulate-failure \
    --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml --failure db
```

See [docs/FAILURE_SIMULATION.md](docs/FAILURE_SIMULATION.md) for all three example
topologies' actual results (one survives a full zone failure; two don't, for different
reasons).

### Assess disaster-recovery readiness

```bash
uv run infraguard assess-recovery \
    --policy examples/recovery/policy.yaml --evidence examples/recovery/evidence.json \
    --as-of 2026-10-19T12:00:00Z
```

Six example workloads, six distinct outcomes — see
[docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md).

### Run a real local recovery drill (optional, needs Docker)

```bash
uv run infraguard recovery-lab drill --workload-id orders-db \
    --policy examples/recovery/policy.yaml --evidence-out live-evidence.json
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml --evidence live-evidence.json
uv run infraguard recovery-lab stop
```

This actually backs up, truncates, restores, and checksum-verifies a disposable Postgres
database in Docker, hard-scoped so it never touches anything outside its own container and
volume — see [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md)'s "Local recovery lab"
section.

### Retrieve a past run, or inspect policy

```bash
uv run infraguard runs
uv run infraguard report --run-id <id> --format markdown
uv run infraguard policy
```

Every module persists its report to one shared SQLite history (`infraguard.db` by default,
override with `--db-path`).

### API

```bash
uv run infraguard serve --reload
```

Then open `http://127.0.0.1:8000/docs` for interactive OpenAPI docs covering the same
capabilities as the CLI above.

## Demo

```bash
make demo
```

Runs [scripts/demo.sh](scripts/demo.sh): all three modules against the committed examples,
in sequence, with explanatory section headers — the same commands in the "Usage" section
above, run for you. See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a narrated,
interview-ready walkthrough of the same tour, and
[examples/sample_outputs/](examples/sample_outputs/) for committed, real output from each
module if you'd rather read than run.

## Example output

Real, unedited excerpts from [examples/sample_outputs/](examples/sample_outputs/) — generated
by actually running the commands above, not written by hand:

**Change analysis** (`analyze-change` on a real `terraform show -json` plan):
```
## Policy decision
- Decision: WARN (exit code 0)
- Reason: 3 finding(s) at or above severity 'medium', below the fail threshold.

### [MEDIUM] 9 attribute(s) of local_file.config are unknown until apply
'local_file.config' has 9 attribute(s) whose final value Terraform cannot determine
from this plan alone... this is a gap, not a clean bill of health.
```

**Failure simulation** (`simulate-failure` on a topology where the app tier *is*
redundant, but shares one database with no redundancy of its own):
```
### [HIGH] 'db' is a single point of failure
Simulating only 'db' failing causes 4 other component(s) to go down...
- Affected resources: app-1, app-2, client, db, lb
```

**Disaster recovery** (`assess-recovery` — this is the central thing the module exists
to catch):
```
### [CRITICAL] No restore has ever been tested for 'billing-db'
A backup's existence is never evidence that it can be restored. No restore drill
record exists for this workload at all.
```
`billing-db` has a backup, and that backup passed its integrity check — and it's still
flagged, because nobody has ever actually restored from it.

## Limitations

Stated here, detailed in each module's own doc — nowhere in this project is a gap hidden
behind an optimistic default:

- **Change analysis**: resource categories are a naming-pattern heuristic across common
  providers, not a real schema; dependency resolution covers the root Terraform module
  only.
- **Failure simulation**: redundancy means "fully interchangeable peers" — which specific
  instance serves a request isn't modeled; no network partitions or correlated failures;
  no availability percentage is ever claimed.
- **Disaster recovery**: only as complete as the evidence you give it — a real backup or
  drill that was never recorded is indistinguishable from one that never happened; the
  local lab implements a truncate-based data-loss scenario, not a full database-replacement
  one.
- **Platform-wide**: this is a static/structural analysis tool. It never touches real cloud
  infrastructure, never runs `terraform apply`/`destroy`, and its conclusions are only as
  good as the input you give it.

See [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) for the trade-offs behind each of
these, and [docs/ROADMAP.md](docs/ROADMAP.md) for what's intentionally not built (and why).

## Status

All 7 milestones complete — see [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)
for exactly what works today, with real verified command output for every milestone, and
[docs/ROADMAP.md](docs/ROADMAP.md) for the acceptance criteria each one met.
