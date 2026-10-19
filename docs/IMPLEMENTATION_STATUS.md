# Implementation Status

Last updated: 2026-10-19

## Current state

**Milestone 0 (repository/environment audit) — done.**
**Milestone 1 (project foundation) — done.**
**Milestone 2 (Terraform Change Impact Analyzer) — done.**
**Milestone 3 (Failure-Domain Simulator) — done.**
**Milestone 4 (Disaster Recovery Readiness Validator, policy layer) — done.**
**Milestone 5 (local Docker/Postgres recovery lab) — done.**
**Milestone 6 (platform integration) — done.**
**Milestone 7 (portfolio polish) — done.**

All 7 milestones are complete. The package installs, the API and CLI both run, SQLite
schema creation is idempotent, and all three modules (A: Terraform change risk, B:
failure-domain simulation, C: recovery readiness including a real local Docker/Postgres
drill lab) are fully implemented, tested, and documented — sharing one SQLite run history
retrievable by `run_id` through both the CLI and the API, a full docs set, a working
`make demo`, and a passing mypy configuration.

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

## Milestone 4: Disaster Recovery Readiness Validator (Module C, policy layer)

```
src/infraguard/modules/disaster_recovery/
  models.py             RecoveryPolicy, BackupEvidence, RestoreDrillRecord,
                          ReadinessDimension (true/false/unknown), WorkloadReadiness
  validator.py            parse_policy_document / parse_evidence_document: fatal vs. valid
  assessor.py               assess_workload(): the 5-dimension evaluation, per workload
  analyzer.py                 Ties it together; cross-references evidence against policy
                                (flags "evidence for unconfigured workload")
api/v1/disaster_recovery.py    POST /api/v1/disaster-recovery/assess-recovery
cli/commands/disaster_recovery.py  `infraguard assess-recovery --policy ... --evidence ...`
examples/recovery/                policy.yaml + evidence.json: 6 workloads, 6 distinct outcomes
```

### Verified commands (actually executed)

```bash
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence examples/recovery/evidence.json --as-of 2026-10-19T12:00:00Z
# -> orders-db: ready / legacy-reports: not_ready / billing-db: insufficient_evidence /
#    analytics-db: not_ready / inventory-db: not_ready / search-index: ready
#    10 finding(s); 4/6 workload(s) not ready.  (exit code 1)

uv run pytest -q   # 158 passed
uv run ruff check src tests   # All checks passed!
```

No bugs were caught by the test suite this milestone — the assessor's branches were
designed against the "5 distinct dimensions, never collapsed" rule from the start, and the
six-workload example was checked against expectations on the first real run.

## Milestone 5: Local Docker/Postgres recovery lab

```
docker/recovery_lab/docker-compose.yml   Single Postgres service, lab-only credentials
src/infraguard/modules/disaster_recovery/lab/
  constants.py        Fixed project/container/db names — not configurable, by design
  compose.py            docker compose / docker-compose fallback probe; up/down/exec wrappers
  availability.py          check_lab_available(): explains the gap when Docker isn't usable
  dataset.py                Deterministic 50-row dataset + SQL-side checksum query
  workflow.py                start/seed/backup/induce_data_loss/restore/run_full_drill
cli/commands/recovery_lab.py   `infraguard recovery-lab start|seed|drill|status|stop`
tests/integration/test_recovery_lab_live.py   Real Docker tests, skip (not fail) if absent
```

### Verified commands (actually executed, against this machine's real Docker/Colima daemon)

```bash
uv run infraguard recovery-lab status
# -> available: yes; running: no

uv run infraguard recovery-lab drill --workload-id orders-db \
    --policy examples/recovery/policy.yaml --evidence-out /tmp/live-evidence.json \
    --backups-dir /tmp/live-backups
# -> backup: lab-backup-20261019T170252Z-39d355 (2219 bytes)
#    restore verification: PASSED in 0.0017 min (RTO 60.0 min); data_loss=0.0 min (RPO 15.0 min)

uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence /tmp/live-evidence.json --as-of "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# -> orders-db: ready, uses_fixture_evidence: False, zero findings for orders-db

uv run infraguard recovery-lab stop
# -> lab stopped; its container and volume were removed.
# docker ps -a / docker volume ls confirmed: zero infraguard-* resources remain,
# and every one of this machine's several unrelated pre-existing containers
# (kubesentinel-control-plane, ai-platform-engineer-*, assorted k8s pods, etc.) untouched.

uv run pytest -q   # 180 passed (includes 5 live-Docker integration tests), ~18s
uv run ruff check src tests   # All checks passed!
```

No bugs were caught by the test suite this milestone; the one real design correction made
during development was choosing to run `pg_dump`/`pg_restore`/`psql` via `docker exec`
inside the container rather than requiring a local PostgreSQL client — confirmed necessary
since this machine has no local `psql` at all (see Milestone 0's audit above).

## Milestone 6: Platform integration

```
src/infraguard/storage/db.py            Schema v2: additive 'runs' table, in-place upgrade
src/infraguard/core/
  reports_store.py    save_report / load_report / list_runs — shared by all 3 modules
  persistence.py        persist_report(): save + audit event, in one call every module uses
  rule_registry.py        Static catalog of every rule_id, module, severity, description
cli/commands/
  reports.py              `infraguard report --run-id ...`, `infraguard runs`
  policy.py                 `infraguard policy [--module ...]`
api/v1/reports.py        GET /api/v1/reports/{run_id}, GET /api/v1/reports
api/v1/policy.py           GET /api/v1/policy
```

Every existing report-producing CLI command and API endpoint (analyze-change,
validate-topology, simulate-failure, assess-recovery) now calls `persist_report` right
after building its `Report` — a cross-cutting change touching all 4.

### Verified commands (actually executed)

```bash
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json \
    --db-path /tmp/m6-test.db --out /tmp/m6-reports
uv run infraguard runs --db-path /tmp/m6-test.db
# -> 2026-10-19T17:15:50...  change_analysis       ed86090348604ea6b19cc8bf63c4ceee
uv run infraguard report --run-id ed86090348604ea6b19cc8bf63c4ceee --db-path /tmp/m6-test.db
# -> the full rendered Markdown report, byte-for-byte the same content originally produced
uv run infraguard policy --module change_analysis
# -> active thresholds + the change_analysis rule catalog

uv run pytest -q   # 203 passed
uv run ruff check src tests   # All checks passed!
```

One real regression was caught and fixed, not shipped silently: adding a `--db-path`
option to every report-producing CLI command meant existing CLI tests that didn't pass one
started writing a real `infraguard.db` into the repository's working directory (confirmed:
a 77 KB file appeared in the repo root after a routine `pytest` run). Fixed by giving every
affected test an isolated `--db-path` under `tmp_path`, and removed the stray file.

## Milestone 7: Portfolio polish

```
docs/THREAT_MODEL.md         Inputs, sensitive data, trust boundaries, lab-specific threats
docs/TESTING.md                Structure, Docker-conditional tests, lint/type-check setup
docs/DESIGN_DECISIONS.md         Trade-offs + alternatives considered, per module
docs/DEMO_SCRIPT.md                Narrated interview walkthrough of scripts/demo.sh
scripts/demo.sh                      make demo: all 3 modules + platform + live lab if present
examples/sample_outputs/               Committed real report output per module
pyproject.toml [tool.mypy]               Added mypy, scoped to src/infraguard
```

### mypy added and made clean (not just configured)

`uv run mypy` found 9 real issues on its first run against the 63-file `src/infraguard`
tree, all fixed (none suppressed with a blanket ignore):

1. `redaction.py`: a local variable named `result` was reused across two branches with
   incompatible inferred types (`dict` in one, `list` in the other) — renamed the second.
2. `core/audit.py`: `sqlite3.Cursor.lastrowid` is typed `int | None`; added an `assert` with
   a one-line comment on why it's always set here (an INSERT into a normal rowid table).
3. `core/models.py`: `Severity`'s `__lt__`/`__gt__`/`__le__`/`__ge__` overrides narrowed
   their parameter type to `Severity`, violating the Liskov substitution principle against
   `str`'s own comparison methods — widened to accept `str` and coerce via `Severity(other)`.
4. `disaster_recovery/assessor.py`: `overall`'s type widened to plain `str` across its
   if/elif branches instead of staying the `Literal[...]` the model field requires — fixed
   with an explicit `Literal[...]` annotation at first assignment.
5. `failure_simulation/simulator.py`: a `dict.get()` without a default produced `str |
   None` where a plain `str` key was needed next — added the same default the subsequent
   lookup already used, with no behavior change.

### Verified commands (actually executed)

```bash
uv run mypy            # -> Success: no issues found in 63 source files
uv run pytest -q       # -> 203 passed
uv run ruff check src tests   # -> All checks passed!
./scripts/demo.sh / make demo  # -> ran all 3 modules + platform integration + the live
                                 #    Docker lab bonus section end-to-end, exit 0
```

### Clean-checkout verification (actually performed)

```bash
git clone /Users/akanksha./Documents/InfraGuard /tmp/clean-checkout-test
cd /tmp/clean-checkout-test
make install   # -> 45 packages resolved, installed cleanly
make test      # -> 203 passed, 1 warning in 18.27s
make demo      # -> ran all 4 sections + the live Docker lab bonus, exit 0
```

Every step passed with no manual intervention beyond those three commands — no local state
from the development checkout leaked in (confirmed separately: the fresh clone's `make
test` run used its own `.venv`, and `make demo`'s live-lab drill produced a fresh
`lab-backup-20261019T174010Z-24c0be` backup, a different id than any run in the main
checkout, proving it wasn't reusing cached state). `docker ps -a` after the run confirmed
the lab's container and volume were removed and nothing else on the machine was touched.
The temporary clone was deleted after verification.

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
| `psql` / `pg_ctl` (local Postgres client/server) | no | — | No bare-metal PostgreSQL install on this machine at all. This is actually convenient: it enforces the constraint that the recovery lab's Postgres only ever runs **inside Docker**, never against a host install. As actually built in Milestone 5, the app runs `pg_dump`/`pg_restore`/`psql` via `docker exec` inside the lab's own container rather than needing any local Postgres client — simpler than adding a `psycopg` dependency, since no Python-side DB driver is needed at all. |
| `terraform` | yes | 1.15.8 | Used only to *generate* example `plan.json` fixtures for docs/demo (`terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json`). InfraGuard itself never invokes `terraform` at runtime — it only parses the JSON produced by that workflow, and tests run against committed static fixture files so they need no network or Terraform install. |

### Implication for the "must still work if Docker is unavailable" requirement

Confirmed as a real scenario on this very machine's history (Docker only recently available
via Colima) — Module A (change analysis) and Module B (failure simulation) have zero Docker
or Postgres dependency by construction, so this requirement is straightforward to satisfy:
those modules only need the `uv`-managed Python environment.

## Historical note

The two subsections that used to follow this toolchain table at Milestone 0 ("What is NOT
yet built" and "Planned first-run commands") are removed now that all 7 milestones are
complete — see "Current state" at the top of this file and each milestone's own section
above for what was actually built and verified, in order.
