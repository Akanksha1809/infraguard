# Module C — Disaster Recovery Readiness Validator

This document covers both the policy/evidence/assessment layer (Milestone 4) and the
optional local Docker/Postgres recovery lab that *produces* real evidence instead of
fixture records (Milestone 5). Everything in the "Policy layer" section works with zero
Docker dependency; the "Local recovery lab" section is additive and entirely optional —
`assess-recovery` never requires it.

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

## Local recovery lab (Milestone 5)

An isolated, disposable Postgres container that actually performs a backup → data-loss →
restore → verify cycle, producing real `source: "live_lab"` evidence instead of
hand-written fixtures — the only thing that distinguishes "we believe this would work" from
"we just watched it work."

### Safety, as code, not just policy

- Every Docker Compose / `docker exec` call is hard-scoped to a fixed project name
  (`infraguard-recovery-lab`), fixed compose file, and fixed container name
  (`infraguard-recovery-lab-postgres`) — see
  [lab/constants.py](../src/infraguard/modules/disaster_recovery/lab/constants.py). None of
  this is a CLI flag or environment variable, so there is no way to point the lab at an
  arbitrary container, volume, or database.
- The "controlled data-loss scenario" is exactly one SQL statement —
  `TRUNCATE TABLE orders;` — against the lab's own database inside the lab's own
  container. Nothing else is ever touched.
- Teardown (`infraguard recovery-lab stop`, or `lab.workflow.stop_lab()`) runs
  `docker compose -p infraguard-recovery-lab down -v --remove-orphans`, which only removes
  resources carrying that project name. **Verified on this project's own dev machine**,
  which has several unrelated pre-existing containers from other projects: running the full
  drill and then `stop` left every other container untouched and removed exactly the lab's
  own container and volume (see the commit history for the actual `docker ps` output this
  was checked against).
- `pg_dump`/`pg_restore`/`psql` run **inside the container** via `docker exec`, so the host
  needs no local PostgreSQL client install — consistent with this machine having none (see
  Milestone 0's audit in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)).

### Workflow

```bash
infraguard recovery-lab start      # 1. start the isolated container
infraguard recovery-lab seed       # 2. populate a deterministic 50-row dataset
infraguard recovery-lab drill \     # 3-9, in one command:
    --workload-id orders-db \       #   backup -> record metadata -> induce data loss ->
    --policy examples/recovery/policy.yaml \   #   restore -> verify -> record duration/outcome
    --evidence-out live-evidence.json
infraguard assess-recovery \        # evaluate the measured result against RTO/RPO
    --policy examples/recovery/policy.yaml --evidence live-evidence.json
infraguard recovery-lab stop       # 10. tear down — only this lab's own resources
```

`drill` starts the lab itself if it isn't already running (idempotent), seeds it, and runs
the entire backup/data-loss/restore/verify cycle in one step; `start`/`stop`/`seed`/`status`
exist separately for manual inspection. `drill` never calls `stop` itself — teardown stays
a separate, explicit action.

### What "verified" means here

The dataset is a deterministic 50-row table (no randomness, so re-seeding always produces
the same fingerprint). Verification compares, before the data loss and after the restore,
a single SQL query's `(row_count, SUM(amount), order-sensitive md5 digest-of-every-row)` —
any missing row, extra row, or altered value changes the digest. Backup "integrity" at this
milestone means `pg_dump` exited cleanly and produced a non-empty file — a structural check,
not a full archive-validity scan (`pg_restore --list`); stated as a limitation, not hidden.

### Actually run, not just designed

This workflow was executed for real against this machine's Docker/Colima daemon while
building this milestone: `start` → `drill` (backup 2219 bytes, restore verification
**PASSED**, checksum digest matched exactly) → the resulting `live_lab` evidence fed into
`assess-recovery`, which correctly reported `orders-db: ready` with
`uses_fixture_evidence: False` and zero findings — then `stop`, confirmed via `docker ps`
to have removed only the lab's own container and volume, leaving every pre-existing
container on the machine untouched.

### Test coverage

`tests/unit/disaster_recovery/lab/` covers the pure-Python logic (deterministic dataset
generation, checksum parsing, the `docker compose`/`docker-compose` fallback probe, and the
availability check) with no Docker required. `tests/integration/test_recovery_lab_live.py`
runs the real thing — start, reseed-is-deterministic, induce-data-loss-empties-the-table,
full-drill-round-trips-data, stop-removes-the-container — and is skipped, with an explicit
reason, on a machine without a working Docker daemon, per the project's "clearly distinguish
optional tests that cannot run due to missing local tools from tests that passed" rule.

### Not implemented (stated, not hidden)

- Only a `TRUNCATE`-based data-loss scenario is implemented ("controlled data-loss"); a
  full database-replacement scenario (drop + recreate the database) is a documented
  possible extension, not silently assumed equivalent.
- No API endpoints trigger the lab — it is CLI-only. Driving a multi-second Docker
  workflow from an HTTP request would need background job handling (status polling, etc.)
  that is out of scope for what this milestone needs; `assess-recovery` (which *consumes*
  the evidence this lab produces) is fully available over the API.
- Backup integrity is a structural check (`pg_dump` succeeded), not a full archive scan.
