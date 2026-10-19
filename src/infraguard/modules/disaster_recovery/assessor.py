"""The readiness assessment: turns one workload's policy + backup/drill evidence into a
`WorkloadReadiness` plus the `Finding`s that justify it.

Five dimensions are evaluated independently and never collapsed into each other — see
models.py's module docstring. A dimension is `UNKNOWN`, never assumed `TRUE`, whenever the
evidence needed to decide it is simply absent.
"""

from datetime import datetime

from infraguard.core.models import Confidence, Finding, Severity
from infraguard.modules.disaster_recovery.models import (
    BackupEvidence,
    ReadinessDimension,
    RecoveryPolicy,
    RestoreDrillRecord,
    WorkloadReadiness,
)


def _latest(items: list, key):
    return max(items, key=key) if items else None


def assess_workload(
    policy: RecoveryPolicy,
    backups: list[BackupEvidence],
    drills: list[RestoreDrillRecord],
    known_workload_ids: set[str],
    as_of: datetime,
) -> tuple[WorkloadReadiness, list[Finding]]:
    findings: list[Finding] = []
    wid = policy.workload_id

    if policy.rto_minutes <= 0 or policy.rpo_minutes <= 0:
        findings.append(
            Finding(
                rule_id="invalid_policy_objective",
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                summary=f"Policy for '{wid}' has a non-positive RTO or RPO",
                detail=(
                    f"rto_minutes={policy.rto_minutes}, rpo_minutes={policy.rpo_minutes}. "
                    "Both must be positive for recovery objectives to mean anything."
                ),
                affected_resources=[wid],
            )
        )

    for dep in policy.depends_on:
        if dep not in known_workload_ids:
            findings.append(
                Finding(
                    rule_id="missing_recovery_dependency",
                    severity=Severity.HIGH,
                    confidence=Confidence.CONFIRMED,
                    summary=f"'{wid}' depends on '{dep}', which has no recovery policy",
                    detail=(
                        f"'{wid}' declares a recovery dependency on '{dep}', but no "
                        f"RecoveryPolicy exists for it — '{dep}'s own recoverability can't "
                        f"be assessed, so '{wid}' cannot be fully trusted to recover either."
                    ),
                    affected_resources=[wid, dep],
                    remediation=f"Define a recovery policy and evidence for '{dep}'.",
                )
            )

    # --- backup_evidence_present ---------------------------------------------------
    backup_evidence_present = bool(backups)
    if not backup_evidence_present:
        findings.append(
            Finding(
                rule_id="no_backup_evidence",
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                summary=f"No backup evidence exists for '{wid}'",
                detail=(
                    "No BackupEvidence record references this workload. A recovery policy "
                    "with no backup evidence behind it is not a safety net."
                ),
                affected_resources=[wid],
                remediation="Record backup evidence (timestamp, retention, integrity check).",
            )
        )

    latest_backup = _latest(backups, key=lambda b: b.taken_at)

    for backup in backups:
        if backup.retention_days < policy.required_retention_days:
            findings.append(
                Finding(
                    rule_id="retention_below_policy",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.CONFIRMED,
                    summary=(
                        f"Backup '{backup.backup_id}' retention ({backup.retention_days}d) "
                        f"is below policy ({policy.required_retention_days}d)"
                    ),
                    detail=(
                        f"'{wid}' requires {policy.required_retention_days} day(s) "
                        f"retention; backup '{backup.backup_id}' declares only "
                        f"{backup.retention_days}."
                    ),
                    affected_resources=[wid],
                    evidence={
                        "backup_id": backup.backup_id,
                        "retention_days": backup.retention_days,
                        "required_retention_days": policy.required_retention_days,
                    },
                )
            )

    if latest_backup is not None:
        age_hours = (as_of - latest_backup.taken_at).total_seconds() / 3600
        if age_hours > policy.max_backup_age_hours:
            findings.append(
                Finding(
                    rule_id="backup_stale",
                    severity=Severity.HIGH,
                    confidence=Confidence.CONFIRMED,
                    summary=f"Most recent backup for '{wid}' is stale ({age_hours:.1f}h old)",
                    detail=(
                        f"Policy requires a backup no older than "
                        f"{policy.max_backup_age_hours}h; the latest "
                        f"('{latest_backup.backup_id}', taken "
                        f"{latest_backup.taken_at.isoformat()}) is {age_hours:.1f}h old as "
                        f"of {as_of.isoformat()}."
                    ),
                    affected_resources=[wid],
                    evidence={
                        "backup_id": latest_backup.backup_id,
                        "age_hours": round(age_hours, 1),
                        "max_backup_age_hours": policy.max_backup_age_hours,
                    },
                )
            )

    # --- backup_integrity_verified --------------------------------------------------
    if latest_backup is None:
        backup_integrity_verified = ReadinessDimension.UNKNOWN
    elif latest_backup.integrity_check_passed is None:
        backup_integrity_verified = ReadinessDimension.UNKNOWN
        if policy.required_integrity_check:
            findings.append(
                Finding(
                    rule_id="backup_integrity_not_checked",
                    severity=Severity.HIGH,
                    confidence=Confidence.CONFIRMED,
                    summary=f"Integrity of the latest backup for '{wid}' was never checked",
                    detail=(
                        "'integrity_check_passed' is not recorded for the most recent "
                        "backup. Its existence is not evidence that it is restorable."
                    ),
                    affected_resources=[wid],
                    evidence={"backup_id": latest_backup.backup_id},
                )
            )
    elif latest_backup.integrity_check_passed is False:
        backup_integrity_verified = ReadinessDimension.FALSE
        findings.append(
            Finding(
                rule_id="backup_integrity_failed",
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                summary=f"Latest backup for '{wid}' failed its integrity check",
                detail=f"Backup '{latest_backup.backup_id}' explicitly failed integrity verification.",
                affected_resources=[wid],
                evidence={"backup_id": latest_backup.backup_id},
            )
        )
    else:
        backup_integrity_verified = ReadinessDimension.TRUE

    # --- restore_successfully_tested -------------------------------------------------
    verified_drills = [d for d in drills if d.verification_passed is True]
    latest_verified_drill = _latest(verified_drills, key=lambda d: d.performed_at)

    if not drills:
        restore_successfully_tested = ReadinessDimension.UNKNOWN
        findings.append(
            Finding(
                rule_id="no_restore_test",
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                summary=f"No restore has ever been tested for '{wid}'",
                detail=(
                    "A backup's existence is never evidence that it can be restored. No "
                    "restore drill record exists for this workload at all."
                ),
                affected_resources=[wid],
                remediation="Run a restore drill and record the result.",
            )
        )
    elif latest_verified_drill is None:
        restore_successfully_tested = ReadinessDimension.FALSE
        findings.append(
            Finding(
                rule_id="restore_test_failed_verification",
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                summary=f"No successfully-verified restore test exists for '{wid}'",
                detail=(
                    "One or more restore drills were recorded, but none has "
                    "verification_passed == true."
                ),
                affected_resources=[wid],
            )
        )
    else:
        restore_successfully_tested = ReadinessDimension.TRUE
        if policy.required_restore_test_interval_days is not None:
            age_days = (as_of - latest_verified_drill.performed_at).days
            if age_days > policy.required_restore_test_interval_days:
                restore_successfully_tested = ReadinessDimension.FALSE
                findings.append(
                    Finding(
                        rule_id="restore_test_stale",
                        severity=Severity.HIGH,
                        confidence=Confidence.CONFIRMED,
                        summary=f"Most recent verified restore test for '{wid}' is stale ({age_days}d old)",
                        detail=(
                            f"Policy requires a restore test within "
                            f"{policy.required_restore_test_interval_days} days; the latest "
                            f"verified drill ('{latest_verified_drill.drill_id}') was "
                            f"{age_days} day(s) ago."
                        ),
                        affected_resources=[wid],
                        evidence={
                            "drill_id": latest_verified_drill.drill_id,
                            "age_days": age_days,
                        },
                    )
                )

    # --- recovery_objectives_demonstrated --------------------------------------------
    if latest_verified_drill is None:
        recovery_objectives_demonstrated = ReadinessDimension.UNKNOWN
    else:
        duration = latest_verified_drill.restore_duration_minutes
        data_loss = latest_verified_drill.data_loss_minutes
        if duration is None or data_loss is None:
            recovery_objectives_demonstrated = ReadinessDimension.UNKNOWN
            findings.append(
                Finding(
                    rule_id="recovery_objective_unmeasured",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.UNKNOWN,
                    summary=f"RTO/RPO cannot be evaluated for '{wid}' from recorded measurements",
                    detail=(
                        "The most recent successfully-verified drill does not record "
                        "restore_duration_minutes and/or data_loss_minutes, so objectives "
                        "cannot be honestly evaluated from it."
                    ),
                    affected_resources=[wid],
                    evidence={"drill_id": latest_verified_drill.drill_id},
                )
            )
        else:
            rto_met = duration <= policy.rto_minutes
            rpo_met = data_loss <= policy.rpo_minutes
            if rto_met and rpo_met:
                recovery_objectives_demonstrated = ReadinessDimension.TRUE
            else:
                recovery_objectives_demonstrated = ReadinessDimension.FALSE
                findings.append(
                    Finding(
                        rule_id="recovery_objective_not_met",
                        severity=Severity.CRITICAL,
                        confidence=Confidence.CONFIRMED,
                        summary=f"Measured recovery for '{wid}' does not meet its RTO/RPO",
                        detail=(
                            f"Drill '{latest_verified_drill.drill_id}' measured "
                            f"restore_duration_minutes={duration} (RTO {policy.rto_minutes}), "
                            f"data_loss_minutes={data_loss} (RPO {policy.rpo_minutes})."
                        ),
                        affected_resources=[wid],
                        evidence={
                            "drill_id": latest_verified_drill.drill_id,
                            "measured_duration_minutes": duration,
                            "rto_minutes": policy.rto_minutes,
                            "rto_met": rto_met,
                            "measured_data_loss_minutes": data_loss,
                            "rpo_minutes": policy.rpo_minutes,
                            "rpo_met": rpo_met,
                        },
                    )
                )

    uses_fixture_evidence = any(d.source == "fixture" for d in drills)
    if uses_fixture_evidence:
        findings.append(
            Finding(
                rule_id="fixture_based_evidence_used",
                severity=Severity.LOW,
                confidence=Confidence.CONFIRMED,
                summary=f"'{wid}' readiness relies on fixture-based drill evidence",
                detail=(
                    "At least one restore drill behind this assessment has source == "
                    "'fixture': supplied as a record, not produced by an actual restore. "
                    "Do not treat this as a live-validated result."
                ),
                affected_resources=[wid],
            )
        )

    if not backup_evidence_present:
        overall = "not_ready"
    elif (
        backup_integrity_verified is ReadinessDimension.FALSE
        or restore_successfully_tested is ReadinessDimension.FALSE
        or recovery_objectives_demonstrated is ReadinessDimension.FALSE
    ):
        overall = "not_ready"
    elif (
        backup_integrity_verified is ReadinessDimension.UNKNOWN
        or restore_successfully_tested is ReadinessDimension.UNKNOWN
        or recovery_objectives_demonstrated is ReadinessDimension.UNKNOWN
    ):
        overall = "insufficient_evidence"
    else:
        overall = "ready"

    readiness = WorkloadReadiness(
        workload_id=wid,
        policy_configured=True,
        backup_evidence_present=backup_evidence_present,
        backup_integrity_verified=backup_integrity_verified,
        restore_successfully_tested=restore_successfully_tested,
        recovery_objectives_demonstrated=recovery_objectives_demonstrated,
        overall=overall,
        uses_fixture_evidence=uses_fixture_evidence,
    )
    return readiness, findings
