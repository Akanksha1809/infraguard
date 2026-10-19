# Module C — Disaster Recovery Readiness Validator (policy layer)

This document covers the policy/evidence/assessment layer built in Milestone 4. The
optional local Docker/Postgres recovery lab that can *produce* real (`source: "live_lab"`)
drill evidence instead of fixture records is Milestone 5 — see
[docs/ROADMAP.md](ROADMAP.md). Everything here works today with no Docker dependency,
using fixture-based evidence, exactly as the project brief requires when Docker/Postgres
is unavailable.

## The central rule

**A backup's existence is never evidence that it is recoverable.** This module exists
specifically to keep that distinction visible instead of letting "we have backups" quietly
stand in for "we can recover." Five questions are tracked completely independently, for
every workload:

1. Is a recovery policy configured at all?
2. Does backup evidence exist?
3. Was that backup's integrity actually verified?
4. Was a restore actually, successfully tested?
5. Did a *measured* restore meet the configured RTO/RPO — not just "succeed," but succeed
   within the stated time and data-loss bounds?

Each is `true`, `false`, or `unknown` — and `unknown` is a real, separate outcome, never
silently treated as either. An assessment's `overall` (`ready` / `not_ready` /
`insufficient_evidence`) is a three-way summary of these five dimensions, always shown
*alongside* every individual finding — never as a replacement for them. There is no
aggregate numeric health score, per the project's explicit constraint against hiding
critical failures behind one number.

## Inputs

Two separate files, matching the brief's CLI example:

```bash
infraguard assess-recovery --policy policy.yaml --evidence evidence.json [--as-of ISO8601]
```

**Policy** (`examples/recovery/policy.yaml`) — one entry per workload:

```yaml
policies:
  - workload_id: orders-db
    name: Orders Database
    rto_minutes: 60
    rpo_minutes: 15
    required_retention_days: 30
    max_backup_age_hours: 24
    required_integrity_check: true
    required_restore_test_interval_days: 90
    depends_on: []          # other workload_ids this one's recovery depends on
```

**Evidence** (`examples/recovery/evidence.json`) — backups and drills, matched to policies
by `workload_id`:

```json
{
  "backups": [{"workload_id": "orders-db", "backup_id": "...", "taken_at": "...", "retention_days": 30, "integrity_check_passed": true}],
  "drills": [{"workload_id": "orders-db", "drill_id": "...", "source": "fixture", "performed_at": "...", "restore_duration_minutes": 42, "verification_passed": true, "data_loss_minutes": 10}]
}
```

`--as-of` pins "now" for staleness calculations, which is what makes this deterministic and
testable rather than dependent on wall-clock time — every test in
`tests/unit/disaster_recovery/` passes a fixed `as_of`, and the committed example is
documented to run with one too (see `examples/recovery/policy.yaml`'s header comment).

## The `source: "fixture" | "live_lab"` distinction

Every `RestoreDrillRecord` states where it came from. `"fixture"` means the record was
supplied in an evidence file, not produced by an actual restore — this module cannot tell
the difference between a real drill and a hand-written one unless the data itself says so,
so it asks the evidence to say so explicitly, and a `fixture_based_evidence_used` finding
calls it out on every workload whose readiness relies on one. `"live_lab"` is reserved for
records the Milestone 5 Docker/Postgres lab produces by actually performing a restore.
**A `"ready"` result built entirely on fixture evidence is clearly labeled as such — it is
never presented as equivalent to a live-validated one.**

## What's checked, and what each finding means

| Finding | Severity | What it means |
|---|---|---|
| `no_backup_evidence` | CRITICAL | No `BackupEvidence` at all for this workload. |
| `backup_integrity_not_checked` | HIGH | Latest backup's `integrity_check_passed` is unrecorded — unknown, not assumed fine. |
| `backup_integrity_failed` | CRITICAL | Latest backup explicitly failed its integrity check. |
| `backup_stale` | HIGH | Latest backup is older than `max_backup_age_hours`. |
| `retention_below_policy` | MEDIUM | A backup's declared `retention_days` is below the policy's requirement. |
| `no_restore_test` | CRITICAL | No restore drill at all exists — **the headline "existence ≠ recoverable" case.** |
| `restore_test_failed_verification` | CRITICAL | Drill(s) exist, but none has `verification_passed == true`. |
| `restore_test_stale` | HIGH | The latest successfully-verified drill is older than `required_restore_test_interval_days`. |
| `recovery_objective_unmeasured` | MEDIUM | A verified drill exists but didn't record duration/data-loss — can't evaluate RTO/RPO honestly. |
| `recovery_objective_not_met` | CRITICAL | A verified drill's *measured* duration or data-loss exceeds RTO/RPO. |
| `missing_recovery_dependency` | HIGH | Declares `depends_on` a workload with no policy of its own. Flags a gap in a *different* workload, so it does not by itself flip this one's `overall` to `not_ready` — see the worked example below. |
| `fixture_based_evidence_used` | LOW | At least one drill behind this result is fixture-sourced, not from a live lab. |
| `evidence_for_unconfigured_workload` | MEDIUM | Evidence references a `workload_id` with no matching policy — can't be assessed at all. |
| `invalid_policy_objective` | HIGH | `rto_minutes` or `rpo_minutes` is zero or negative. |

"Most recent" is always the latest `taken_at`/`performed_at` compared against `as_of`.

## Validation (fatal vs. structural)

Fatal (raises `InputValidationError`, exit code 2): document root not an object, schema
validation failure (wrong types, missing required fields), duplicate `workload_id` across
policies. These mean there is no sound document to assess.

## CI exit codes

Simpler than Module A's configurable-threshold policy engine, because here the "policy" is
the recovery objectives themselves, not a separate severity gate:

- **0** — every assessed workload is `ready`.
- **1** — at least one workload is `not_ready` or `insufficient_evidence`. Per the brief's
  "never let missing evidence silently become a passing result," `insufficient_evidence`
  is treated the same as `not_ready` for CI purposes — it is not a pass.
- **2** — the policy or evidence document itself was invalid (see Validation above).

## Worked example (run, not just described)

`examples/recovery/policy.yaml` + `examples/recovery/evidence.json` define six workloads,
each isolating one outcome. Running
`infraguard assess-recovery --policy examples/recovery/policy.yaml --evidence examples/recovery/evidence.json --as-of 2026-10-19T12:00:00Z`
actually produces:

| Workload | `overall` | Why |
|---|---|---|
| `orders-db` | `ready` | Fresh integrity-checked backup + a recent verified drill meeting RTO 60m/RPO 15m. |
| `legacy-reports` | `not_ready` | No backup evidence at all. |
| `billing-db` | `insufficient_evidence` | Backup exists and passed integrity, but **no restore has ever been tested.** |
| `analytics-db` | `not_ready` | A drill ran, but its verification explicitly failed. |
| `inventory-db` | `not_ready` | A *verified* drill ran, but measured 55 min / 20 min of data loss against a 30 min RTO / 5 min RPO policy. |
| `search-index` | `ready` (with a HIGH finding) | Otherwise fully ready, but depends on `missing-service`, which has no policy — flagged, not hidden, without flipping this workload's own verdict. |

4 of 6 workloads are not ready; the CLI exits 1.

## Known limitations (stated, not hidden)

- This is only as complete as the evidence supplied — a real backup or drill that was never
  recorded is indistinguishable from one that never happened.
- `depends_on` is a flat, one-level declaration (this workload depends on that one); it is
  not a full dependency graph like Module B's topology model.
- No numeric aggregate health score is produced anywhere in this module's output.
