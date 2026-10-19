# Design Decisions

A consolidated list of the trade-offs made while building InfraGuard, with the alternative
considered and why it was rejected. Each entry links to where the decision actually lives
in code or in a module's own doc, so this file is a map, not a duplicate.

## Platform-level

**`uv` instead of Poetry.** Equivalent lockfile/reproducible-install capability, already
present on the dev machine, and can provision a pinned Python 3.12 without relying on the
system's aging Python 3.9.6. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)'s
Milestone 0 audit.

**SQLite with no migration framework**, additive-only schema changes tracked by a single
`schema_version` row (now at v2). Alternative considered: Alembic. Rejected as
disproportionate for a single-user local tool with two schema versions so far; revisit if
a future change needs to be destructive (a column removal/rename) rather than additive —
see `storage/db.py`'s docstring and `tests/unit/test_db_upgrade.py`.

**No unified cross-module "policy engine."** Module A has genuine configurable severity
thresholds; Modules B and C have fixed rule sets with fixed severities, because a SPOF is a
SPOF and a missing restore test is always CRITICAL — there is nothing meaningful to
threshold. Inventing a shared configuration shape across all three would have been a false
abstraction forced onto problems that don't share that shape. See
[POLICY_REFERENCE.md](POLICY_REFERENCE.md).

**A numeric risk score exists (Module A) but never decides anything.** The brief is
explicit that an unexplained number must never itself approve or reject a change, and that
an aggregate health score must never hide critical findings. `risk_score.py` is
informational, capped, and explained; `policy.py`'s pass/fail/warn/error decision is driven
only by explicit severity thresholds over named findings.

**Confidence (`confirmed` / `heuristic` / `unknown`) is tracked on every finding,
separately from severity.** A fact read directly from input (an action is "delete") is
`confirmed`; a graph-derived or pattern-matched conclusion (a resource "category," a SPOF
determination) is `heuristic`; a genuine evidence gap is `unknown` and never silently
promoted to either. This shows up identically across all three modules by design, so a
reviewer only learns the vocabulary once.

## Module A — Change Analysis

**Resource categories are a substring-pattern heuristic**, not a real provider schema.
Building (or vendoring) an actual multi-provider resource schema was out of scope; the
pattern list is explicit and documented as a heuristic in every finding it produces (see
[CHANGE_ANALYSIS.md](CHANGE_ANALYSIS.md)), rather than silently presented as authoritative.

**Dependency extraction covers the root module only.** Recursing into `module_calls` for
nested-module resources is a real feature a production tool would need; it was deferred
rather than half-implemented, with an explicit `module_scoped_dependencies_unsupported`
warning so the gap is visible in every report it affects, not silently incomplete.

**Secret redaction uses two independent signals** (Terraform's own sensitivity marks, plus
a key-name heuristic), because relying on either alone would under-redact: a provider that
forgets to mark a field sensitive, or a value whose key name doesn't match the pattern,
would otherwise leak. Over-redaction (flagging a harmless `credentials` field wholesale) is
the accepted cost of the safer direction.

## Module B — Failure Simulation

**Redundancy means "fully interchangeable peers"** — which specific instance serves a
request is not modeled. A weighted/partial-routing model was considered and rejected as
unjustified complexity for a structural simulator whose job is "does this survive at all,"
not "exactly how is load distributed." Stated explicitly in
[FAILURE_SIMULATION.md](FAILURE_SIMULATION.md) rather than left implicit.

**SPOF detection is "simulate failing this one thing alone,"** not a graph-theoretic
articulation-point calculation. This was a deliberate choice: it reuses the exact same
cascading-failure engine every other scenario uses (one code path, one set of tests to
trust), and it naturally produces the right answer for redundancy groups without any
special-casing, at the cost of being `O(components)` simulations instead of one graph
traversal — a non-issue at the scale this tool targets.

## Module C — Disaster Recovery

**Five dimensions, never collapsed, and no aggregate health score anywhere in this
module's output.** This is the brief's single most emphasized constraint for Module C
("a backup's existence must never imply it is recoverable"), so it was treated as the
starting design constraint rather than a feature bolted on afterward — see
[DISASTER_RECOVERY.md](DISASTER_RECOVERY.md)'s central-rule section.

**A `missing_recovery_dependency` finding does not, by itself, flip a workload's `overall`
verdict to `not_ready`.** It flags a gap in a *different* workload's own readiness, not
this one's backup/restore evidence — conflating the two would make the five-dimension
model lie about what it actually measured for the workload at hand. The finding is still
surfaced at HIGH severity, so nothing is hidden; see
`test_missing_recovery_dependency_flagged` for the test that pins this down.

**The local lab runs `pg_dump`/`pg_restore`/`psql` via `docker exec`, not a local Postgres
client.** This machine (like most without a dedicated Postgres install) has no local
`psql`; shelling into the container sidesteps that dependency entirely and is also just how
a real operator would do a Postgres drill without installing client tools everywhere.

**The lab's Postgres credentials are a hardcoded, committed, public string.** This is
correct, not an oversight: the container is disposable, localhost-only, created and
destroyed by the same tool run, and never holds real data. Treating it as a secret worth
rotating or hiding would be theater — see [THREAT_MODEL.md](THREAT_MODEL.md).

**The lab is CLI-only; no API endpoint triggers a drill.** Driving a multi-second Docker
workflow from an HTTP request needs background-job handling (status polling, a job queue)
that is disproportionate to what this milestone needs. `assess-recovery`, which *consumes*
whatever evidence the lab produces, is fully available over the API regardless.

**Only a `TRUNCATE`-based data-loss scenario is implemented**, not a full
drop-and-recreate-the-database variant the brief also allows ("a controlled data-loss *or*
database replacement scenario" — either satisfies it). Implementing one scenario
thoroughly, safely, and tested was preferred over implementing two superficially; stated as
a known limitation in [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md), not silently assumed
equivalent.

## Things deliberately not built

Kubernetes, a message broker, a microservices split, a frontend framework, mypy in
`--strict` mode, and a bespoke migration framework — none were justified by the problem at
this scale; see the Roadmap's "Not planned unless a real need appears" section.
