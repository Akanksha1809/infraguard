from datetime import timedelta

from infraguard.modules.disaster_recovery.assessor import assess_workload
from infraguard.modules.disaster_recovery.models import ReadinessDimension


def test_fully_ready_workload(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(rto_minutes=60, rpo_minutes=15)
    backup = backup_factory(taken_at=as_of - timedelta(hours=2))
    drill = drill_factory(
        performed_at=as_of - timedelta(days=5),
        restore_duration_minutes=42,
        data_loss_minutes=10,
        verification_passed=True,
    )
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)

    assert readiness.overall == "ready"
    assert readiness.backup_evidence_present is True
    assert readiness.backup_integrity_verified is ReadinessDimension.TRUE
    assert readiness.restore_successfully_tested is ReadinessDimension.TRUE
    assert readiness.recovery_objectives_demonstrated is ReadinessDimension.TRUE
    assert not any(f.severity.value in ("high", "critical") for f in findings)


def test_no_backup_evidence_is_not_ready(policy_factory, as_of) -> None:
    policy = policy_factory()
    readiness, findings = assess_workload(policy, [], [], {"wl"}, as_of)

    assert readiness.overall == "not_ready"
    assert readiness.backup_evidence_present is False
    assert any(f.rule_id == "no_backup_evidence" for f in findings)


def test_backup_but_no_drill_is_insufficient_evidence(policy_factory, backup_factory, as_of) -> None:
    # The central point of this module: a backup's existence is never evidence it's recoverable.
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    readiness, findings = assess_workload(policy, [backup], [], {"wl"}, as_of)

    assert readiness.overall == "insufficient_evidence"
    assert readiness.restore_successfully_tested is ReadinessDimension.UNKNOWN
    assert any(f.rule_id == "no_restore_test" for f in findings)


def test_drill_with_failed_verification_is_not_ready(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1), verification_passed=False)
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)

    assert readiness.overall == "not_ready"
    assert readiness.restore_successfully_tested is ReadinessDimension.FALSE
    assert any(f.rule_id == "restore_test_failed_verification" for f in findings)


def test_measured_recovery_exceeding_objectives_is_not_ready(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory(rto_minutes=30, rpo_minutes=5)
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(
        performed_at=as_of - timedelta(days=1),
        verification_passed=True,
        restore_duration_minutes=55,
        data_loss_minutes=20,
    )
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)

    assert readiness.overall == "not_ready"
    assert readiness.recovery_objectives_demonstrated is ReadinessDimension.FALSE
    finding = next(f for f in findings if f.rule_id == "recovery_objective_not_met")
    assert finding.evidence["rto_met"] is False
    assert finding.evidence["rpo_met"] is False


def test_verified_drill_without_measurements_is_unknown_not_assumed_passing(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(
        performed_at=as_of - timedelta(days=1),
        verification_passed=True,
        restore_duration_minutes=None,
        data_loss_minutes=None,
    )
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)

    assert readiness.recovery_objectives_demonstrated is ReadinessDimension.UNKNOWN
    assert readiness.overall == "insufficient_evidence"
    assert any(f.rule_id == "recovery_objective_unmeasured" for f in findings)


def test_stale_backup_flagged(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(max_backup_age_hours=24)
    backup = backup_factory(taken_at=as_of - timedelta(hours=48))
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    _, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert any(f.rule_id == "backup_stale" for f in findings)


def test_fresh_backup_not_flagged_stale(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(max_backup_age_hours=24)
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    _, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert not any(f.rule_id == "backup_stale" for f in findings)


def test_retention_below_policy_flagged(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(required_retention_days=30)
    backup = backup_factory(taken_at=as_of - timedelta(hours=1), retention_days=7)
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    _, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    finding = next(f for f in findings if f.rule_id == "retention_below_policy")
    assert finding.evidence["retention_days"] == 7


def test_stale_restore_test_flagged(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(required_restore_test_interval_days=30)
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=90), verification_passed=True)
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert readiness.restore_successfully_tested is ReadinessDimension.FALSE
    assert any(f.rule_id == "restore_test_stale" for f in findings)


def test_backup_integrity_not_checked_is_unknown(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory(required_integrity_check=True)
    backup = backup_factory(taken_at=as_of - timedelta(hours=1), integrity_check_passed=None)
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert readiness.backup_integrity_verified is ReadinessDimension.UNKNOWN
    assert readiness.overall == "insufficient_evidence"
    assert any(f.rule_id == "backup_integrity_not_checked" for f in findings)


def test_backup_integrity_failed_is_not_ready(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1), integrity_check_passed=False)
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert readiness.backup_integrity_verified is ReadinessDimension.FALSE
    assert readiness.overall == "not_ready"
    assert any(f.rule_id == "backup_integrity_failed" for f in findings)


def test_missing_recovery_dependency_flagged(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory(depends_on=["other-service"])
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert any(f.rule_id == "missing_recovery_dependency" for f in findings)
    # A missing dependency is its own concern, not one of the five readiness dimensions —
    # it does not by itself flip an otherwise-ready workload to not_ready.
    assert readiness.overall == "ready"


def test_satisfied_recovery_dependency_not_flagged(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory(depends_on=["other-service"])
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1))
    _, findings = assess_workload(policy, [backup], [drill], {"wl", "other-service"}, as_of)
    assert not any(f.rule_id == "missing_recovery_dependency" for f in findings)


def test_fixture_source_labeled(policy_factory, backup_factory, drill_factory, as_of) -> None:
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1), source="fixture")
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert readiness.uses_fixture_evidence is True
    assert any(f.rule_id == "fixture_based_evidence_used" for f in findings)


def test_live_lab_source_not_labeled_as_fixture(
    policy_factory, backup_factory, drill_factory, as_of
) -> None:
    policy = policy_factory()
    backup = backup_factory(taken_at=as_of - timedelta(hours=1))
    drill = drill_factory(performed_at=as_of - timedelta(days=1), source="live_lab")
    readiness, findings = assess_workload(policy, [backup], [drill], {"wl"}, as_of)
    assert readiness.uses_fixture_evidence is False
    assert not any(f.rule_id == "fixture_based_evidence_used" for f in findings)


def test_invalid_policy_objective_flagged(backup_factory, drill_factory, as_of, policy_factory) -> None:
    policy = policy_factory(rto_minutes=0, rpo_minutes=15)
    _, findings = assess_workload(policy, [], [], {"wl"}, as_of)
    assert any(f.rule_id == "invalid_policy_objective" for f in findings)
