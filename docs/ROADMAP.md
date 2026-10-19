# InfraGuard Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done (acceptance criteria met
and verified by running the stated commands/tests).

## Milestone 0 — Repository and environment audit

**Status: `[~]` in progress — stopped here for review, per instructions.**

Acceptance criteria:
- [x] Directory, git state, and local tooling inspected and recorded
  ([IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)).
- [x] Proposed architecture documented ([ARCHITECTURE.md](ARCHITECTURE.md)).
- [x] This roadmap exists with acceptance criteria for every milestone.
- [ ] User has reviewed and approved the plan before Milestone 1 begins.

## Milestone 1 — Project foundation

**Status: `[x]` done.**

Goal: a package that installs, a CLI/API that start, and a test suite that runs — with
no feature logic yet.

Acceptance criteria — all verified by actually running the commands:
- [x] `uv sync --extra dev` creates a working venv from `pyproject.toml` (Python 3.12.15,
  38 packages).
- [x] `uv run infraguard --help` prints the CLI skeleton (`version`, `serve` commands).
- [x] `uv run uvicorn infraguard.api.app:create_app --factory` serves `/api/v1/health`,
  `/api/v1/ready`, and `/docs` (OpenAPI UI) — confirmed with live `curl` requests
  (200 responses) against a running instance, then torn down.
- [x] SQLite schema creation (`infraguard.storage.db.init_db`) runs idempotently and creates
  `schema_version` + `audit_events`.
- [x] `uv run pytest` passes: 9/9 tests (health, readiness, schema init/idempotency, audit
  event recording, structured error shape, CLI help/version).
- [x] `uv run ruff check src tests` passes with zero findings.
- [x] Structured JSON logging (`infraguard.logging_config`) and a consistent
  `{"error": {"code", "message", "details"}}` error shape (`infraguard.errors` +
  a FastAPI exception handler) exist and are exercised by `tests/unit/test_errors.py`.

What this milestone deliberately does NOT include: no `core/inventory.py`, `graph.py`,
`policies.py`, or `reporting.py` yet — those are built starting Milestone 2, against real
module requirements, rather than as empty placeholders now.

## Milestone 2 — Terraform Change Impact Analyzer (Module A)

**Status: `[x]` done.**

Goal: a complete, demonstrable feature — not a stub.

Acceptance criteria — all verified by actually running the commands:
- [x] `infraguard analyze-change --plan examples/terraform/sample/plan.json` runs against a
  **real** plan — `plan.json` was produced by actually running
  `terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json`
  against the committed local-only (`random`/`local` provider) example config, not
  hand-written — and produces both JSON and Markdown reports. Dependency extraction was
  confirmed working against this real output (recovered both an implicit reference and an
  explicit `depends_on` edge correctly).
- [x] Fixtures (`tests/fixtures/change_analysis/`, 13 files) cover: create, update, delete,
  both replace orderings (with and without reported `replace_paths`), no-op, a data-source
  read, an explicit+implicit dependency chain, nested unknown values, Terraform-marked and
  heuristic sensitive values, an unsupported resource type, a module-scoped resource, and
  four malformed-input shapes — each with tests in `tests/unit/change_analysis/`.
- [x] Secret-looking values are redacted via two independent signals (Terraform's own
  sensitivity marks + a key-name heuristic); `tests/unit/change_analysis/test_redaction.py`
  and `test_parser.py::test_redacts_sensitive_values_while_parsing` assert this, including
  the case Terraform did *not* mark.
- [x] CI exit codes come from `policy.py`'s explicit severity thresholds, never the
  risk score; `test_policy.py::test_parse_warning_findings_fail_closed_by_default` proves a
  strict policy fails closed (exit 2) on incomplete input rather than passing.
- [x] `docs/CHANGE_ANALYSIS.md` documents resource categories, every risk rule, the
  dependency-graph scope/limitations, redaction, risk score, and the policy/exit-code table.
- [x] `make test` (78 tests, all passing) and `make lint` (ruff, clean) both pass.

## Milestone 3 — Failure-Domain Simulator (Module B)

**Status: `[x]` done.**

Acceptance criteria — all verified by actually running the commands:
- [x] 3 example topologies committed under `examples/topologies/` (fragile single-instance,
  redundant app with shared-DB bottleneck, multi-zone with real redundancy). Each was
  actually run through `simulate-failure`: the fragile and shared-DB-bottleneck topologies
  cascade to full outage from one failure; the multi-zone topology survives a full
  failure-domain loss with **zero** cascaded findings — a concrete, run-verified
  demonstration that redundancy design (not just redundancy count) determines the outcome.
- [x] `infraguard validate-topology --file <f>` reports duplicate ids, unknown references,
  self-loops, and cycles without crashing (`tests/unit/failure_simulation/test_validator.py`).
- [x] `infraguard simulate-failure --topology <f> --failure <id> [--failure-domain <d>]`
  computes blast radius, SPOFs, redundancy gaps, and surviving capacity (where capacity
  data is complete) for both single- and multi-component/domain failures.
- [x] `test_redundant_pair_app_instances_are_not_spofs` proves a redundant peer removes a
  component from the SPOF list; `test_failing_entire_redundancy_group_cascades` proves
  failing *all* peers at once does cascade — the direction changes exactly as expected.
- [x] `docs/FAILURE_SIMULATION.md` states the exact down/redundancy/capacity model, the
  three example topologies' actual results, and explicit limitations (no availability
  percentage claimed anywhere).
- [x] `make test` (123 tests, all passing) and `make lint` (ruff, clean) both pass.

## Milestone 4 — Disaster Recovery Readiness Validator (Module C, policy layer)

Acceptance criteria:
- Recovery policy schema (RTO/RPO, retention) + evidence schema (backup timestamps,
  integrity, restore-test results) implemented and validated.
- Readiness assessment output clearly separates: policy configured / backup evidence present
  / integrity verified / restore tested / objectives demonstrated by measurement — a test
  asserts these never collapse into one boolean.
- Stale backups, missing evidence, and failed restores are each covered by a fixture + test.
- Fixture-based (non-live) evidence is labeled as such in every report it appears in.
- `docs/DISASTER_RECOVERY.md` written.

## Milestone 5 — Local recovery lab (optional, Docker/Postgres)

Acceptance criteria:
- `docker compose` (with documented `docker-compose` fallback — see
  [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)) brings up an isolated, InfraGuard-
  prefixed Postgres instance with no effect on any pre-existing container on the machine.
- End-to-end script: start lab → seed deterministic data → backup → simulate data loss →
  restore → verify checksums → record measured duration → evaluate against RTO/RPO → tear
  down only the named lab resources.
- A safety test asserts the teardown path only ever targets resources carrying the lab's
  own project/name prefix.
- If Docker is unavailable, `make test` still passes in full by skipping (and clearly
  labeling as skipped, not silently passing) only the Docker-dependent tests.

## Milestone 6 — Platform integration

Acceptance criteria:
- All three modules reachable through both the CLI and the versioned FastAPI routes, sharing
  one SQLite history/audit trail.
- `infraguard report --run-id <id> --format markdown|json` retrieves any past run's report.
- Policy engine inspection endpoint/command lists active rules and thresholds.

## Milestone 7 — Portfolio polish

Acceptance criteria:
- `make demo` runs a scripted, reproducible tour of all three modules from a clean checkout.
- Full docs set complete: README, ARCHITECTURE, THREAT_MODEL, CHANGE_ANALYSIS,
  FAILURE_SIMULATION, DISASTER_RECOVERY, POLICY_REFERENCE, TESTING, DESIGN_DECISIONS,
  DEMO_SCRIPT, ROADMAP (this file, updated).
- A reviewer can clone, `uv sync`, `make test`, `make demo` with no manual steps beyond what
  the README states, and no external account/API key at any point.

## Not planned unless a real need appears

Kubernetes, message brokers, microservices split, paid cloud resources, a migration
framework, or a frontend framework beyond a simple server-rendered or static dashboard.
