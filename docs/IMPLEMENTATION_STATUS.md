# Implementation Status

Last updated: 2026-10-19

## Current state

**Milestone 0 (repository/environment audit) — done.**
**Milestone 1 (project foundation) — done.**
**Milestone 2 (Terraform Change Impact Analyzer) — done.**
**Milestone 3 (Failure-Domain Simulator) — done.**

The package installs, the API and CLI both run, SQLite schema creation is idempotent, and
Modules A (Terraform change risk) and B (failure-domain simulation) are fully implemented,
tested, and documented. Disaster Recovery (Module C) does not exist yet — that starts at
Milestone 4.

### What exists now

```
src/infraguard/
  config.py            Settings (env-prefixed, INFRAGUARD_*), all fields have safe local defaults
  errors.py            InfraGuardError hierarchy -> {"error": {code, message, details}}
  logging_config.py     stdlib logging + JSON formatter, no extra dependency
  core/
    audit.py           record_event()/list_events() against the shared SQLite audit log
  storage/
    db.py              sqlite3 connection + idempotent schema creation, schema_version table
  api/
    app.py             create_app() factory: wires settings, logging, DB init, error handler
    v1/health.py       GET /api/v1/health (liveness), GET /api/v1/ready (DB check)
  cli/
    app.py             Typer app: `infraguard version`, `infraguard serve [--reload]`
tests/
  unit/                9 tests covering all of the above
Makefile                install / lint / test / demo targets
```

### Verified commands (actually executed, not assumed)

```bash
uv sync --extra dev        # -> 38 packages installed, Python 3.12.15
uv run pytest -v           # -> 9 passed
uv run ruff check src tests  # -> All checks passed!
uv run infraguard --help   # -> prints version/serve commands
uv run infraguard version  # -> 0.1.0
uv run uvicorn infraguard.api.app:create_app --factory --port 8321
curl .../api/v1/health     # -> {"status":"ok"}
curl .../api/v1/ready      # -> {"status":"ok","schema_version":"1"}
curl .../docs              # -> HTTP 200
```

One bug was caught and fixed during this verification: `get_schema_version` originally
raised `sqlite3.OperationalError` instead of returning `None` when called before `init_db`
had ever run (table didn't exist yet). Fixed by checking `sqlite_master` first; covered by
`tests/unit/test_db.py::test_init_db_creates_schema`.

## Milestone 2: Terraform Change Impact Analyzer (Module A)

```
src/infraguard/core/
  models.py            Shared Severity/Confidence/Finding/PolicyDecision/Report models
  graph.py             NetworkX wrapper: build_graph, dependents_of, dependencies_of
  reporting.py         render_json() / render_markdown() for any module's Report
src/infraguard/modules/change_analysis/
  models.py            ChangeAction, ResourceCategory, ResourceChange, ParsedPlan
  redaction.py          Terraform-mark + key-name-heuristic secret redaction
  categories.py          Resource-type -> category pattern matching
  dependencies.py        depends_on + implicit-reference extraction (root module)
  parser.py              parse_plan(): raw JSON -> ParsedPlan, fatal vs recoverable errors
  rules.py                7 deterministic risk rules -> Findings
  risk_score.py           Informational, capped, explained score (never drives policy)
  policy.py               PolicyConfig + evaluate_policy(): fail-closed CI decision
  analyzer.py             Ties it together; file-size/JSON validation
api/v1/change_analysis.py  POST /api/v1/change-analysis/analyze
cli/commands/change_analysis.py  `infraguard analyze-change`
examples/terraform/sample/  Real local-only (random/local provider) config + generated plan.json
examples/policies/            default.yaml, strict.yaml
```

### Verified commands (actually executed)

```bash
cd examples/terraform/sample && terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json
# -> ran for real: "Plan: 3 to add, 0 to change, 0 to destroy."

uv run infraguard analyze-change --plan examples/terraform/sample/plan.json
# -> 3 finding(s); policy decision: warn — exit code 0

uv run python -c "... parse_plan(real plan.json) ..."
# -> dependency_edges correctly included both an implicit reference
#    (local_file.config -> random_pet.suffix) and an explicit depends_on
#    (local_file.readme -> local_file.config), confirming the dependency
#    extraction works against genuine Terraform output, not only fixtures.

uv run pytest -q   # full suite, including all change_analysis tests
uv run ruff check src tests   # clean
```

Two bugs were caught and fixed by the test suite during this milestone (not shipped
silently): `parse_plan` originally treated a wholly missing `resource_changes` key as "zero
changes" instead of a fatal input error (now raises `InputValidationError`, per "a missing
field is never evidence of safety"); and the redaction heuristic's whole-subtree match on a
key like `credentials` was initially exercised by a test that assumed partial nested
redaction instead of the (correct, documented) wholesale redaction — the test was fixed to
match the intended behavior, and a second test was added to pin down the wholesale-redaction
case explicitly.

## Milestone 3: Failure-Domain Simulator (Module B)

```
src/infraguard/modules/failure_simulation/
  models.py            Component, Dependency, Topology, FailureScenario
  validator.py           parse_topology(): fatal vs. non-fatal (warning) issues
  grouping.py             Redundancy-group / "logical node" membership helpers
  simulator.py             Monotonic fixed-point cascading-failure propagation
  capacity.py                Surviving-capacity ratios (only when data is complete)
  analysis.py                 SPOF detection, redundancy-gap detection, scenario findings
  analyzer.py                  Ties it together; YAML/JSON file loading + size validation
api/v1/failure_simulation.py    POST .../validate-topology, POST .../simulate-failure
cli/commands/failure_simulation.py  `infraguard validate-topology`, `infraguard simulate-failure`
examples/topologies/              3 example topologies (see docs/FAILURE_SIMULATION.md)
```

### Verified commands (actually executed)

```bash
uv run infraguard validate-topology --file examples/topologies/fragile-single-instance.yaml
uv run infraguard simulate-failure --topology examples/topologies/fragile-single-instance.yaml --failure app
# -> 3 component(s) down total (2 cascaded); 10 finding(s)

uv run infraguard simulate-failure --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml --failure db
# -> 5 component(s) down total (4 cascaded); 10 finding(s) -- shared DB takes down both
#    "redundant" app instances despite the app tier itself having no SPOF

uv run infraguard simulate-failure --topology examples/topologies/multi-zone-redundant.yaml --failure-domain zone-a
# -> 3 component(s) down total (0 cascaded); 6 finding(s) -- full zone loss, zero cascade

uv run pytest -q   # 123 passed
uv run ruff check src tests   # All checks passed!
```

Three test/fixture bugs were caught and fixed during this milestone, not shipped silently:
(1) a test asserted `simple_chain.yaml` would parse with zero warnings, missing that a
topology with no declared `failure_domain` correctly produces a
`no_failure_domains_declared` warning; (2 and 3) two SPOF tests assumed every component in a
chain/redundant-pair fixture would be a SPOF, which is wrong by the model's own correct
logic — a component nothing depends on (the "root" of a dependency chain, or a load
balancer with no client-equivalent pointing at it in that minimal fixture) can never be a
SPOF, since failing it alone has no one left to affect. The `redundant_pair.yaml` fixture
was corrected to include a `client` depending on `lb` so the test's original intent (lb has
no redundancy, the app tier does) is actually exercised.

## Repository audit

- Working directory (`/Users/akanksha./Documents/InfraGuard`) was completely empty before
  this session — no source files, no config, no `.git`.
- Not yet a git repository. Proposal: `git init` with an initial commit of the Milestone 0
  docs, once reviewed, so all subsequent milestones are tracked incrementally.

## Local toolchain audit (macOS, Darwin 24.6.0, Apple Silicon/arm64)

| Tool | Found | Version | Notes / Decision |
|---|---|---|---|
| `python3` (system) | yes | 3.9.6 (`/usr/bin/python3`, Apple CLT) | Too old to target directly (EOL soon, misses newer typing syntax). **Not used as the project interpreter.** |
| Homebrew Python | yes | 3.12.15 (`/opt/homebrew/bin/python3.12`) | Usable directly, but see `uv` below. |
| `uv` | yes | 0.12.24 | **Chosen packaging/venv tool.** Can provision and pin a Python 3.12 interpreter and manage a lockfile without Poetry. Replaces the `poetry`-style flow implied by the brief; Poetry itself is not installed and not needed. |
| `poetry` | no | — | Not installed; not required since `uv` covers the same job with less setup. |
| `pip` | yes | 21.2.4 (tied to system Python 3.9) | Not used directly; `uv` manages dependencies. |
| `git` | yes | 2.50.1 | — |
| `make` | yes | GNU Make 3.81 (Apple CLT, circa 2006) | Old but sufficient for simple, portable Makefile targets (`install`, `lint`, `test`, `demo`). Avoid relying on modern GNU Make 4.x–only features. |
| `docker` (CLI) | yes | 29.6.1, context `colima` | Daemon is up via Colima (not Docker Desktop). 1 running + 16 stopped containers already exist on this machine from unrelated prior work — **InfraGuard will never touch containers/volumes it did not create itself**, and all lab resources will use an explicit, InfraGuard-prefixed project name. |
| `docker compose` (CLI plugin subcommand) | no | — | `docker compose version` reports "unknown command" under this CLI/Colima context, even though a plugin shim is present in `~/.docker/cli-plugins/`. |
| `docker-compose` (standalone binary) | yes | 5.3.1 (`/opt/homebrew/bin/docker-compose`) | **Fallback that works today.** Module C tooling/Makefile will try `docker compose` first and fall back to `docker-compose` automatically, documented plainly rather than assumed. |
| `psql` / `pg_ctl` (local Postgres client/server) | no | — | No bare-metal PostgreSQL install on this machine at all. This is actually convenient: it enforces the constraint that the recovery lab's Postgres only ever runs **inside Docker**, never against a host install. The Python app will speak to Postgres via a Python driver (`psycopg[binary]`, bundles its own libpq) rather than shelling out to `psql`. |
| `terraform` | yes | 1.15.8 | Used only to *generate* example `plan.json` fixtures for docs/demo (`terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json`). InfraGuard itself never invokes `terraform` at runtime — it only parses the JSON produced by that workflow, and tests run against committed static fixture files so they need no network or Terraform install. |

### Implication for the "must still work if Docker is unavailable" requirement

Confirmed as a real scenario on this very machine's history (Docker only recently available
via Colima) — Module A (change analysis) and Module B (failure simulation) have zero Docker
or Postgres dependency by construction, so this requirement is straightforward to satisfy:
those modules only need the `uv`-managed Python environment.

## What is NOT yet built

Everything in Modules A/B/C, the shared platform (models, policy engine, SQLite persistence,
API, CLI), and all tests. Milestone 1 starts that work after this audit is reviewed.

## Planned first-run commands (not functional yet)

These are the target commands once Milestone 1 (foundation) and Milestone 2 (Module A) land —
listed now so the roadmap's acceptance criteria are concrete, not because they run today:

```bash
# Milestone 1+
uv sync                       # create venv, install deps from pyproject.toml/uv.lock
uv run pytest                 # run unit test suite
uv run infraguard --help      # CLI entry point

# Milestone 2 (Module A demo)
uv run infraguard analyze-change --plan examples/terraform/plan.json
```

No command above has been executed as a real InfraGuard command yet (`uv`, `docker`,
`terraform`, `git` version checks above were run directly against the OS to audit tooling,
not against this project).
