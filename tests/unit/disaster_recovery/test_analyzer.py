from datetime import UTC, datetime

import pytest

from infraguard.errors import InputValidationError
from infraguard.modules.disaster_recovery.analyzer import assess_recovery_files


def test_end_to_end_assessment(fixture_path) -> None:
    report = assess_recovery_files(
        fixture_path("policy_valid.yaml"),
        fixture_path("evidence_valid.json"),
        as_of=datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC),
    )
    assert report.module == "disaster_recovery"
    readiness = {r["workload_id"]: r for r in report.inputs["readiness"]}
    assert readiness["wl"]["overall"] == "ready"


def test_orphan_evidence_flagged(fixture_path) -> None:
    report = assess_recovery_files(
        fixture_path("policy_valid.yaml"),
        fixture_path("evidence_valid.json"),
        as_of=datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC),
    )
    assert any(
        f.rule_id == "evidence_for_unconfigured_workload" and "orphan-workload" in f.affected_resources
        for f in report.findings
    )


def test_missing_policy_file_raises(tmp_path, fixture_path) -> None:
    with pytest.raises(InputValidationError):
        assess_recovery_files(tmp_path / "missing.yaml", fixture_path("evidence_valid.json"))


def test_invalid_yaml_syntax_raises(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        assess_recovery_files(fixture_path("invalid_yaml_syntax.yaml"), fixture_path("evidence_valid.json"))


def test_default_as_of_is_now(fixture_path) -> None:
    # No explicit as_of: should use real "now" and not crash. The fixture's backup is
    # old relative to real "now", so it will be stale/insufficient, but that's expected —
    # this test only confirms the default path runs without error.
    report = assess_recovery_files(fixture_path("policy_valid.yaml"), fixture_path("evidence_valid.json"))
    assert report.inputs["as_of"] is not None
