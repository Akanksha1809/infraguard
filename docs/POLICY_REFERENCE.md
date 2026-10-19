# Policy Reference

InfraGuard does not have one unified "policy engine" that every module plugs into with the
same configuration shape — that would be a false abstraction, since the three modules
answer genuinely different questions. Instead:

- **Module A (Terraform change analysis)** has an actual configurable, severity-threshold
  CI policy (`PolicyConfig`), described fully in
  [docs/CHANGE_ANALYSIS.md](CHANGE_ANALYSIS.md#policy-and-ci-exit-codes).
- **Module B (failure simulation)** and **Module C (disaster recovery)** have a fixed set
  of rules with fixed severities. There is nothing to threshold — a SPOF is a SPOF, and a
  missing restore test is always CRITICAL. Module C's CI exit codes come from the
  three-way `overall` readiness verdict, not a tunable severity gate (see
  [docs/DISASTER_RECOVERY.md](DISASTER_RECOVERY.md#ci-exit-codes)).

This document is the one place that lists every rule_id across all three modules in one
table, and shows how to inspect what's active.

## Inspecting policy

```bash
infraguard policy [--module change_analysis|failure_simulation|disaster_recovery]
```

```
GET /api/v1/policy
```

Both return: Module A's active default `PolicyConfig` (the thresholds `analyze-change`
uses unless you pass `--policy`), and the full rule catalog below.

## The complete rule catalog

Source of truth: [src/infraguard/core/rule_registry.py](../src/infraguard/core/rule_registry.py).
Keep that file, this table, and the per-module docs in sync when a rule changes.

| Module | Rule ID | Default severity | What it means |
|---|---|---|---|
| change_analysis | `destructive_delete` | varies by category | A resource is being deleted. |
| change_analysis | `destructive_replace` | varies by category | A resource is being replaced. |
| change_analysis | `sensitive_category_mutation` | MEDIUM | A database/storage/IAM/networking resource is touched by any action. |
| change_analysis | `unknown_after_values` | MEDIUM | Attributes are unknown until apply. |
| change_analysis | `unsupported_resource_type` | MEDIUM | A destructive change targets an unmodeled resource type. |
| change_analysis | `dependents_affected` | HIGH | Other resources statically depend on one being removed/replaced. |
| change_analysis | `parse_warning.*` | MEDIUM | A resource entry couldn't be fully parsed (fails closed under the default strict policy). |
| failure_simulation | `single_point_of_failure` | HIGH | Failing this component alone takes others down with it. |
| failure_simulation | `dependency_without_redundancy` | MEDIUM | A required dependency's target has no redundant peer. |
| failure_simulation | `component_failed_explicit` | HIGH | A component was directly failed by the scenario. |
| failure_simulation | `component_down_cascaded` | HIGH | A component goes down as a consequence, with the causing dependency named in `evidence`. |
| failure_simulation | `capacity_degraded` | MEDIUM | A redundancy group survives but at reduced capacity. |
| failure_simulation | `topology_warning.*` | LOW–MEDIUM | A structural topology issue (cycle, single-member group, etc.). |
| disaster_recovery | `no_backup_evidence` | CRITICAL | No backup evidence exists for a workload. |
| disaster_recovery | `backup_integrity_not_checked` | HIGH | The latest backup's integrity was never checked. |
| disaster_recovery | `backup_integrity_failed` | CRITICAL | The latest backup explicitly failed integrity verification. |
| disaster_recovery | `backup_stale` | HIGH | The latest backup is older than the policy's max age. |
| disaster_recovery | `retention_below_policy` | MEDIUM | A backup's retention is below what the policy requires. |
| disaster_recovery | `no_restore_test` | CRITICAL | No restore has ever been tested — a backup's existence is never evidence it's recoverable. |
| disaster_recovery | `restore_test_failed_verification` | CRITICAL | Drill(s) exist, but none passed verification. |
| disaster_recovery | `restore_test_stale` | HIGH | The latest verified drill is older than the required interval. |
| disaster_recovery | `recovery_objective_unmeasured` | MEDIUM | A verified drill didn't record duration/data-loss. |
| disaster_recovery | `recovery_objective_not_met` | CRITICAL | A verified drill's measured RTO/RPO was exceeded. |
| disaster_recovery | `missing_recovery_dependency` | HIGH | A declared recovery dependency has no policy of its own. |
| disaster_recovery | `fixture_based_evidence_used` | LOW | The result relies on fixture, not live-lab, drill evidence. |
| disaster_recovery | `evidence_for_unconfigured_workload` | MEDIUM | Evidence exists for a workload with no policy. |
| disaster_recovery | `invalid_policy_objective` | HIGH | A policy's RTO or RPO is zero or negative. |

## Run history and audit

Every module, through both the CLI and the API, persists its `Report` (full findings,
policy decision, inputs) to SQLite via `core.persistence.persist_report`, and records a
summary audit event (`core.audit.record_event`). Retrieve any past run:

```bash
infraguard report --run-id <id> [--format json|markdown]
infraguard runs [--module change_analysis] [--limit 20]
```

```
GET /api/v1/reports/{run_id}
GET /api/v1/reports?module=...&limit=...
```

This is schema v2 of the shared SQLite database (`runs` table, additive over v1's
`audit_events`) — see [storage/db.py](../src/infraguard/storage/db.py) for the additive
upgrade strategy.
