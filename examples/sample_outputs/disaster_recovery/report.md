# InfraGuard Report — disaster_recovery

- **Run ID:** `67374c1aff464f31a164a1430e52d001`
- **Created:** 2026-10-19T17:35:36.819622+00:00
- **Schema version:** 1

## Findings (10)

### [CRITICAL] No backup evidence exists for 'legacy-reports' (`no_backup_evidence`, confidence: confirmed)

No BackupEvidence record references this workload. A recovery policy with no backup evidence behind it is not a safety net.

- **Affected resources:** legacy-reports
- **Remediation:** Record backup evidence (timestamp, retention, integrity check).

### [CRITICAL] No restore has ever been tested for 'legacy-reports' (`no_restore_test`, confidence: confirmed)

A backup's existence is never evidence that it can be restored. No restore drill record exists for this workload at all.

- **Affected resources:** legacy-reports
- **Remediation:** Run a restore drill and record the result.

### [CRITICAL] No restore has ever been tested for 'billing-db' (`no_restore_test`, confidence: confirmed)

A backup's existence is never evidence that it can be restored. No restore drill record exists for this workload at all.

- **Affected resources:** billing-db
- **Remediation:** Run a restore drill and record the result.

### [CRITICAL] No successfully-verified restore test exists for 'analytics-db' (`restore_test_failed_verification`, confidence: confirmed)

One or more restore drills were recorded, but none has verification_passed == true.

- **Affected resources:** analytics-db

### [CRITICAL] Measured recovery for 'inventory-db' does not meet its RTO/RPO (`recovery_objective_not_met`, confidence: confirmed)

Drill 'inventory-drill-2026-10-10' measured restore_duration_minutes=55.0 (RTO 30.0), data_loss_minutes=20.0 (RPO 5.0).

- **Affected resources:** inventory-db
- **Evidence:** `{'drill_id': 'inventory-drill-2026-10-10', 'measured_duration_minutes': 55.0, 'rto_minutes': 30.0, 'rto_met': False, 'measured_data_loss_minutes': 20.0, 'rpo_minutes': 5.0, 'rpo_met': False}`

### [HIGH] 'search-index' depends on 'missing-service', which has no recovery policy (`missing_recovery_dependency`, confidence: confirmed)

'search-index' declares a recovery dependency on 'missing-service', but no RecoveryPolicy exists for it — 'missing-service's own recoverability can't be assessed, so 'search-index' cannot be fully trusted to recover either.

- **Affected resources:** search-index, missing-service
- **Remediation:** Define a recovery policy and evidence for 'missing-service'.

### [LOW] 'orders-db' readiness relies on fixture-based drill evidence (`fixture_based_evidence_used`, confidence: confirmed)

At least one restore drill behind this assessment has source == 'fixture': supplied as a record, not produced by an actual restore. Do not treat this as a live-validated result.

- **Affected resources:** orders-db

### [LOW] 'analytics-db' readiness relies on fixture-based drill evidence (`fixture_based_evidence_used`, confidence: confirmed)

At least one restore drill behind this assessment has source == 'fixture': supplied as a record, not produced by an actual restore. Do not treat this as a live-validated result.

- **Affected resources:** analytics-db

### [LOW] 'inventory-db' readiness relies on fixture-based drill evidence (`fixture_based_evidence_used`, confidence: confirmed)

At least one restore drill behind this assessment has source == 'fixture': supplied as a record, not produced by an actual restore. Do not treat this as a live-validated result.

- **Affected resources:** inventory-db

### [LOW] 'search-index' readiness relies on fixture-based drill evidence (`fixture_based_evidence_used`, confidence: confirmed)

At least one restore drill behind this assessment has source == 'fixture': supplied as a record, not produced by an actual restore. Do not treat this as a live-validated result.

- **Affected resources:** search-index


## Assumptions

- A backup's existence is never treated as evidence that it is recoverable — integrity verification and a successfully-verified restore test are tracked as separate facts.
- A dimension (integrity verified / restore tested / objectives demonstrated) is only ever TRUE or FALSE when there is direct evidence for it; otherwise it is UNKNOWN, never defaulted to either.
- 'Most recent' backup/drill is determined by the latest 'taken_at'/'performed_at' timestamp in the supplied evidence, compared against the 'as_of' time (default: now).

## Limitations

- This assessment is only as complete as the supplied evidence document — it cannot detect a backup or drill that happened but was never recorded.
- Fixture-based drill evidence (source: 'fixture') is clearly labeled wherever it contributes to a 'ready' result, but is not itself a live-validated restore — see Milestone 5's local recovery lab for that.
- No overall numeric health score is produced; 'overall' is a three-way outcome shown alongside every individual finding, never a substitute for them.

## Recommended next steps

- 3 workload(s) are NOT READY: legacy-reports, analytics-db, inventory-db.
- 1 workload(s) have insufficient evidence to assess: billing-db.
