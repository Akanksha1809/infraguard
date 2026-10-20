from pathlib import Path

import pytest

from infraguard.core.models import Confidence, Finding, Severity
from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.policy import PolicyConfig, evaluate_policy, load_policy_config


def _finding(rule_id: str, severity: Severity, evidence: dict | None = None) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        summary="x",
        detail="x",
        evidence=evidence or {},
    )


def test_pass_when_no_findings() -> None:
    decision = evaluate_policy([], PolicyConfig())
    assert decision.decision == "pass"
    assert decision.exit_code == 0


def test_warn_below_fail_threshold() -> None:
    decision = evaluate_policy([_finding("r", Severity.MEDIUM)], PolicyConfig())
    assert decision.decision == "warn"
    assert decision.exit_code == 0


def test_fail_at_or_above_threshold() -> None:
    decision = evaluate_policy([_finding("r", Severity.HIGH)], PolicyConfig())
    assert decision.decision == "fail"
    assert decision.exit_code == 1


def test_parse_warning_findings_fail_closed_by_default() -> None:
    findings = [_finding("parse_warning.resource_change_missing_address", Severity.MEDIUM)]
    decision = evaluate_policy(findings, PolicyConfig())
    assert decision.decision == "error"
    assert decision.exit_code == 2


def test_parse_warning_can_be_downgraded_explicitly() -> None:
    findings = [_finding("parse_warning.resource_change_missing_address", Severity.MEDIUM)]
    decision = evaluate_policy(findings, PolicyConfig(strict_on_parse_warnings=False))
    assert decision.decision == "warn"


def test_known_limitation_parse_warning_does_not_fail_closed() -> None:
    # fails_closed=False means "the input is fine, our coverage of it is incomplete" --
    # a strict policy must not treat this the same as a genuinely malformed resource.
    findings = [
        _finding(
            "parse_warning.module_scoped_dependencies_unsupported",
            Severity.MEDIUM,
            evidence={"fails_closed": False},
        )
    ]
    decision = evaluate_policy(findings, PolicyConfig())
    assert decision.decision == "warn"
    assert decision.exit_code == 0


def test_mixed_fatal_and_known_limitation_warnings_still_fails_closed() -> None:
    # One genuinely fatal warning alongside one known-limitation warning must still
    # trip the strict error path -- the fix narrows what counts as fatal, it doesn't
    # weaken the guarantee that a real parse problem is never waved through.
    findings = [
        _finding(
            "parse_warning.module_scoped_dependencies_unsupported",
            Severity.MEDIUM,
            evidence={"fails_closed": False},
        ),
        _finding(
            "parse_warning.resource_change_missing_address",
            Severity.MEDIUM,
            evidence={"fails_closed": True},
        ),
    ]
    decision = evaluate_policy(findings, PolicyConfig())
    assert decision.decision == "error"
    assert decision.exit_code == 2
    assert len(decision.triggered_finding_ids) == 1  # only the fatal one is named


def test_custom_thresholds_from_yaml(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("fail_on_severity_at_or_above: critical\nwarn_on_severity_at_or_above: low\n")

    config = load_policy_config(policy_file)

    assert config.fail_on_severity_at_or_above is Severity.CRITICAL
    decision = evaluate_policy([_finding("r", Severity.HIGH)], config)
    assert decision.decision == "warn"


def test_malformed_policy_yaml_raises(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("fail_on_severity_at_or_above: [this, is, not, a, severity]\n")

    with pytest.raises(InputValidationError):
        load_policy_config(policy_file)


def test_missing_policy_file_uses_defaults() -> None:
    config = load_policy_config(None)
    assert config == PolicyConfig()
