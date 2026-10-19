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

Goal: a complete, demonstrable feature — not a stub.

Acceptance criteria:
- `infraguard analyze-change --plan <file>` runs against a committed example `plan.json` and
  produces both JSON and Markdown reports.
- Fixtures cover: create, update, delete, replace, no-op, a dependency chain, unknown/unknown
  values, and at least one malformed/adversarial input — each with an expected-output test.
- Secret-looking values in plan output are redacted in reports; a test asserts this.
- CI exit codes are driven by configurable policy thresholds, not a bare numeric score; a
  test proves a strict policy fails closed on invalid input (never fails open).
- `docs/CHANGE_ANALYSIS.md` documents supported resource categories, risk rules, and stated
  limitations.
- `make test` and `make lint` pass.

## Milestone 3 — Failure-Domain Simulator (Module B)

Acceptance criteria:
- At least 3 example topologies committed (fragile single-instance, redundant app with
  shared-DB bottleneck, multi-zone with real redundancy), each with a documented expected
  result.
- `infraguard validate-topology --file <f>` reports missing/invalid references with no
  crashes on malformed input.
- `infraguard simulate-failure --topology <f> --failure <id>` computes blast radius, SPOFs,
  unreachable components, and (where capacity data exists) surviving capacity, for single and
  multi-component failures.
- A test proves changing topology redundancy changes the simulation result in the expected
  direction (e.g., adding a replica removes a previously-flagged SPOF).
- `docs/FAILURE_SIMULATION.md` states the graph/availability model and its explicit
  limitations (no claim of real-world probability without a stated model).

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
