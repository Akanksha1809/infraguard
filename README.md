# InfraGuard

**Infrastructure reliability and resilience engineering, entirely on your own machine.**
No cloud account, no paid API, no credentials, and no network access required for any
mandatory functionality — the one optional capability that touches Docker explains itself
plainly when Docker isn't there, instead of failing silently.

## What it is, and why

Before a risky infrastructure change goes out, an SRE or platform engineer actually wants
three questions answered — and most tooling answers at most one of them:

1. **Can this change introduce risk?** Terraform plans get applied based on a diff that's
   often skimmed, not analyzed.
2. **What happens if part of the infrastructure fails?** Redundancy is usually assumed,
   not verified against the actual dependency graph.
3. **Can the infrastructure actually recover?** "We have backups" is routinely mistaken
   for "we can recover" — those are not the same claim.

InfraGuard answers all three locally, through one consistent reporting format (JSON +
Markdown, a shared `Finding`/`Severity`/`Confidence` vocabulary, one CI-friendly policy
decision per run), and it says so plainly whenever it can't answer confidently rather than
guessing. Nowhere does it claim more certainty than static analysis can actually support —
no invented availability percentages, no unexplained numeric "health score," no treating a
backup's mere existence as proof it's recoverable.

## How it actually works

### Module A — Terraform change impact analysis

Parses the JSON from `terraform show -json` (never runs `terraform apply`/`destroy` — it
only reads a plan that was already produced). For every resource change it:

- classifies the action (create / update / delete / replace in either ordering / no-op /
  read), read directly from the plan's `actions` list — never guessed;
- categorizes the resource (database / storage / IAM / networking / compute / other) by a
  documented substring-pattern heuristic across common provider naming conventions — this
  is stated as a heuristic everywhere it's used, not presented as a real provider schema;
- builds a dependency graph (NetworkX) from the plan's own `depends_on` and implicit
  `references` metadata, so it can tell you what *else* breaks if a resource is removed;
- redacts secrets with two independent signals — Terraform's own `sensitive` marks, plus a
  key-name heuristic that catches values a provider forgot to mark — before any value ever
  reaches a report; the redacted before/after values are then shown directly in
  destructive-change findings, so a reviewer can see exactly what's changing without the
  risk of a leaked credential;
- applies deterministic risk rules (same plan in → same findings out, always) producing a
  severity (LOW–CRITICAL), a confidence level (confirmed / heuristic / unknown — a
  category match is heuristic, an action read from the plan is confirmed, a genuine gap in
  the data is unknown and never silently assumed safe), and a remediation suggestion;
- computes an informational risk score (a capped, explained sum of finding severities) that
  **never** drives the pass/fail decision by itself;
- reaches one policy decision — `pass` / `warn` / `fail` / `error` — driven only by
  configurable severity thresholds over named findings, with a distinct CI exit code for
  each, so it's safe to wire directly into a pipeline gate.

### Module B — failure-domain simulation

Takes a declarative topology (YAML/JSON: components, required/optional dependencies,
redundancy groups, failure domains, capacity) and:

- validates it (duplicate ids, dangling references, self-loops are fatal; a dependency
  cycle or a single-member redundancy group is a reported warning, not a crash);
- simulates failing one or more components, or an entire failure domain at once, by
  propagating failure through *required* dependencies as a monotonic fixed point — a
  component goes down only if it's explicitly failed, or if **every** member of a required
  dependency's redundancy group is down (an optional dependency never propagates failure);
- finds single points of failure by literally simulating every component failing alone and
  checking whether anything else goes down with it — reusing the exact same propagation
  engine as every other scenario, so there's only one algorithm to trust;
- flags required dependencies whose target has no redundancy at all, as a static check
  independent of any specific scenario;
- computes surviving capacity per redundancy group, but **only** when every member of that
  group declares a capacity value — a missing value is reported as genuinely unknown, never
  assumed to be zero or full.

It never claims a real-world availability percentage. It tells you, given exactly the
topology you described, what happens — and names its own limitations (no network
partitions, no correlated failures, redundancy means "fully interchangeable peers") in
every report.

### Module C — disaster recovery readiness

Takes a recovery policy (RTO, RPO, retention, max backup age, required restore-test
cadence, declared recovery dependencies) and an evidence document (backup timestamps and
integrity checks, restore-drill records), and evaluates **five dimensions independently,
never collapsed into one score**:

1. is a policy configured;
2. does backup evidence exist;
3. was that backup's integrity actually verified;
4. was a restore actually, successfully tested;
5. did a *measured* restore meet the configured RTO/RPO.

Each dimension is `true`, `false`, or `unknown` — and `unknown` is a real outcome, never
silently defaulted to passing. **A backup's existence is never, by itself, evidence that it
is recoverable** — that's the one rule this whole module exists to enforce.

It can also *produce* real evidence instead of only accepting hand-written evidence: an
optional local Docker/Postgres lab spins up an isolated, disposable Postgres container,
seeds a deterministic dataset, backs it up, truncates the table (a scoped, explicit,
hardcoded data-loss scenario — never anything broader), restores from the backup, and
verifies the restore with a SQL-side checksum — writing the real measured duration and
outcome back as evidence. Every container, volume, and command this touches is hard-scoped
to a fixed project/container name baked into the code, never a configurable flag, so it can
never be pointed at a real database by accident.

### The platform underneath all three

One shared `Report` model (findings, policy decision, assumptions, limitations, next
steps) and one renderer (JSON + Markdown) — a reviewer learns the vocabulary once, not
three times. Every run, from any module, through either interface, is persisted to one
SQLite history and retrievable later by id. A policy-inspection command/endpoint states
plainly which thresholds are genuinely configurable (Module A's) and which rule sets are
fixed (Modules B and C) — no unified "policy engine" is pretended into existing where one
doesn't.

## Architecture

A modular monolith, not microservices: one Python package, one FastAPI app, one CLI, one
SQLite database, three independent module subpackages built on shared primitives (models,
a NetworkX-backed graph helper, the report renderer, an audit/persistence layer). Full
diagram and the reasoning behind it: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The
trade-offs behind specific choices (`uv` over Poetry, no migration framework, `docker exec`
over a local Postgres client, why there's no unified policy engine, and more) are in
[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md).

## Install

```bash
git clone https://github.com/Akanksha1809/infraguard && cd infraguard
make install   # uv sync --extra dev
```

Requires Python 3.12+ (managed automatically by `uv`) and, optionally, Docker — only for
the recovery lab below. Everything else needs nothing beyond `uv`.

## Demos — every module, run for real

Every command and every line of output below is real — copy-pasted from actually running
this code, not written from expectation. Run them yourself with the commands shown.

### 1. Terraform change impact analysis

```bash
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json
```

That `plan.json` is genuine `terraform show -json` output (from a local-only config using
the `random`/`local` providers — no cloud account needed to regenerate it yourself; see
[docs/CHANGE_ANALYSIS.md](docs/CHANGE_ANALYSIS.md) for the exact three commands). Real
output:

```
## Policy decision
- Decision: WARN (exit code 0)
- Reason: 3 finding(s) at or above severity 'medium', below the fail threshold.

### [MEDIUM] 9 attribute(s) of local_file.config are unknown until apply
'local_file.config' has 9 attribute(s) whose final value Terraform cannot determine
from this plan alone... this is a gap, not a clean bill of health.
```

A plan that deletes a database looks different —
`uv run infraguard analyze-change --plan tests/fixtures/change_analysis/delete_database.json`
comes back `CRITICAL`, exit code 1, with the specific finding named in the decision.

### 2. Failure-domain simulation — same shape, three redundancy designs, three different outcomes

```bash
uv run infraguard simulate-failure --topology examples/topologies/fragile-single-instance.yaml --failure app
uv run infraguard simulate-failure --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml --failure db
uv run infraguard simulate-failure --topology examples/topologies/multi-zone-redundant.yaml --failure-domain zone-a
```

Client → load balancer → app → database, each example built the same way, with
increasingly real redundancy:

**No redundancy anywhere** — losing one app instance takes down everything above it:
```
### [HIGH] 'app' is a single point of failure
Simulating only 'app' failing causes 2 other component(s) to go down...
```

**The app tier *is* redundant (two instances) — but shares one database with none.**
Losing the database still cascades to a full outage, because tier-level redundancy alone
doesn't save you from a shared dependency with none of its own:
```
### [HIGH] 'db' is a single point of failure
Simulating only 'db' failing causes 4 other component(s) to go down...
- Affected resources: app-1, app-2, client, db, lb

### [HIGH] 'app-1' goes down as a consequence
'app-1' was not directly failed, but goes down due to a required dependency on 'db',
whose redundancy group (db) is entirely down.
```

**Every tier duplicated across two zones.** Losing an entire zone at once produces **zero**
SPOF or cascade findings — only the explicit failures and a correctly-computed 50%
remaining capacity:
```
### [HIGH] 'app-1' fails in this scenario
### [HIGH] 'db-primary' fails in this scenario
### [HIGH] 'lb-a' fails in this scenario
### [MEDIUM] 'app' is at 50.0% capacity
```
No `single_point_of_failure`, no `component_down_cascaded` — same simulator, same code
path, genuinely different result because the topology is genuinely different.

### 3. Disaster recovery readiness — six workloads, six distinct outcomes

```bash
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence examples/recovery/evidence.json --as-of 2026-10-19T12:00:00Z
```

```
  orders-db: ready
  legacy-reports: not_ready
  billing-db: insufficient_evidence
  analytics-db: not_ready
  inventory-db: not_ready
  search-index: ready
10 finding(s); 4/6 workload(s) not ready.
```

The one worth reading closely is `billing-db` — it has a backup, and that backup passed
its integrity check, and it's still flagged:
```
### [CRITICAL] No restore has ever been tested for 'billing-db'
A backup's existence is never evidence that it can be restored. No restore drill
record exists for this workload at all.
```

### 4. The real recovery lab (needs Docker)

```bash
uv run infraguard recovery-lab drill --workload-id orders-db \
    --policy examples/recovery/policy.yaml --evidence-out live-evidence.json
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml --evidence live-evidence.json
uv run infraguard recovery-lab stop
```

This actually backs up, truncates, restores, and checksum-verifies a disposable Postgres
database — not a fixture. Real output:
```
backup: lab-backup-20261019T170252Z-39d355 (2219 bytes)
restore verification: PASSED in 0.0017 min (RTO 60.0 min); data_loss=0.0 min (RPO 15.0 min)
```
The resulting evidence is tagged `source: live_lab`; `assess-recovery` reports
`uses_fixture_evidence: false` for it, so a live-validated result is never confused with a
fixture-backed one. `recovery-lab stop` tears down only this lab's own container and
volume — scoped in code, not just by convention, and verified by running it on a machine
with several unrelated containers from other projects already running, untouched.

### 5. Platform integration — history and policy, across every module

```bash
uv run infraguard runs
uv run infraguard report --run-id <id> --format markdown
uv run infraguard policy
```

```
2026-10-19T17:35:36  disaster_recovery    67374c1aff464f31a164a1430e52d001
2026-10-19T17:35:36  failure_simulation   cf3b395941244352b7e9dc2a13082a34
2026-10-19T17:35:35  change_analysis      a0b2b8676650438a832cfd1220eb10c6
```
Every run from every module, through either the CLI or the API, lands in one history,
retrievable later by id.

### 6. The whole tour in one command

```bash
make demo
```

Runs [scripts/demo.sh](scripts/demo.sh): all three modules above, in sequence, with
section headers, plus the live Docker lab bonus if Docker is available. See
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a narrated, interview-ready walkthrough of
the same tour, and [examples/sample_outputs/](examples/sample_outputs/) for more committed,
real reports if you'd rather read than run.

### 7. The API

```bash
uv run infraguard serve --reload
```

Open `http://127.0.0.1:8000/docs` for interactive OpenAPI docs covering everything above —
the CLI and the API are two faces of the same service layer, not two implementations.

## Testing and quality

```bash
make lint      # ruff
make typecheck # mypy, scoped to src/infraguard
make test      # pytest — 209 tests, ~20s, including live Docker integration tests
```

The Docker-dependent tests (`tests/integration/`) check once whether Docker is actually
usable and skip with an explicit reason when it isn't — never silently passing, never
failing a machine that simply doesn't have Docker. Fixtures deliberately cover adversarial
input: malformed JSON, missing fields, unknown resource types, dependency cycles,
Terraform-marked and heuristically-caught sensitive values, zero-evidence workloads. See
[docs/TESTING.md](docs/TESTING.md) for the full breakdown and
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for what's trusted, what isn't, and why the
local recovery lab can't be pointed at anything outside itself.

## Limitations

Stated here, detailed in each module's own doc — nowhere in this project is a gap hidden
behind an optimistic default:

- **Change analysis**: resource categories are a naming-pattern heuristic across common
  providers, not a real schema; dependency resolution covers the root Terraform module
  only (resources inside child modules get an explicit, non-fatal warning, not a silent
  gap).
- **Failure simulation**: redundancy means "fully interchangeable peers" — which specific
  instance actually serves a request isn't modeled; no network partitions or correlated
  failures; no availability percentage is ever claimed.
- **Disaster recovery**: only as complete as the evidence you give it — a real backup or
  drill that was never recorded is indistinguishable from one that never happened; the
  local lab implements a truncate-based data-loss scenario, not a full
  database-replacement one.
- **Platform-wide**: this is a static/structural analysis tool. It never touches real
  cloud infrastructure, never runs `terraform apply`/`destroy`, and its conclusions are
  only as good as the input you give it — it has been stress-tested against larger and
  more varied synthetic inputs than its bundled examples, but not against the full variety
  of real-world production Terraform/topology/recovery data.

## Documentation

| Doc | Covers |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component diagram, data flow, module boundaries |
| [CHANGE_ANALYSIS.md](docs/CHANGE_ANALYSIS.md) | Module A: every rule, the redaction model, the policy/exit-code table |
| [FAILURE_SIMULATION.md](docs/FAILURE_SIMULATION.md) | Module B: the precise failure/redundancy/capacity model and all three example topologies' results |
| [DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | Module C: the five-dimension model and the local recovery lab's safety scoping |
| [POLICY_REFERENCE.md](docs/POLICY_REFERENCE.md) | The complete rule catalog across all three modules, and what's actually configurable |
| [DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) | Trade-offs and alternatives considered, module by module |
| [THREAT_MODEL.md](docs/THREAT_MODEL.md) | Trust boundaries, sensitive data handling, lab-specific threats |
| [TESTING.md](docs/TESTING.md) | Test structure, the Docker-conditional-test convention, lint/type-check setup |
| [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | A narrated walkthrough of `make demo`, for presenting this project live |
