"""The CI policy decision: fails closed on invalid/incomplete input, and is driven by
explicit severity thresholds over findings — never by the aggregate risk score.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from infraguard.core.models import Finding, PolicyDecision, Severity
from infraguard.errors import InputValidationError


class PolicyConfig(BaseModel):
    fail_on_severity_at_or_above: Severity = Severity.HIGH
    warn_on_severity_at_or_above: Severity = Severity.MEDIUM
    strict_on_parse_warnings: bool = True
    """If True, any parse_warning.* finding whose underlying ParseWarning is marked
    fails_closed=True causes an ERROR decision (exit code 2), regardless of other
    findings — InfraGuard never treats incompletely-parsed input as a clean result just
    because no other severity threshold was crossed. A parse_warning.* finding marked
    fails_closed=False (a known, stated coverage limitation rather than a data problem —
    e.g. an unresolved module-scoped dependency) does not trigger this: the input itself
    is fine, so it falls through to the ordinary severity-threshold checks below like any
    other MEDIUM finding."""


def load_policy_config(path: Path | None) -> PolicyConfig:
    if path is None:
        return PolicyConfig()
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise InputValidationError(f"Policy file '{path}' is not valid YAML: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise InputValidationError(f"Policy file '{path}' must contain a YAML mapping.")
    try:
        return PolicyConfig.model_validate(raw)
    except ValidationError as exc:
        raise InputValidationError(f"Policy file '{path}' failed validation: {exc}") from exc


def evaluate_policy(findings: list[Finding], config: PolicyConfig) -> PolicyDecision:
    fatal_parse_warnings = [
        f
        for f in findings
        if f.rule_id.startswith("parse_warning.") and f.evidence.get("fails_closed", True)
    ]
    if fatal_parse_warnings and config.strict_on_parse_warnings:
        return PolicyDecision(
            decision="error",
            exit_code=2,
            reason=(
                f"{len(fatal_parse_warnings)} parse warning(s) present and "
                "strict_on_parse_warnings is enabled; failing closed on incomplete/invalid "
                "input rather than analyzing around it."
            ),
            triggered_finding_ids=[f.id for f in fatal_parse_warnings],
        )

    failing = [f for f in findings if f.severity >= config.fail_on_severity_at_or_above]
    if failing:
        return PolicyDecision(
            decision="fail",
            exit_code=1,
            reason=(
                f"{len(failing)} finding(s) at or above severity "
                f"'{config.fail_on_severity_at_or_above.value}'."
            ),
            triggered_finding_ids=[f.id for f in failing],
        )

    warning = [f for f in findings if f.severity >= config.warn_on_severity_at_or_above]
    if warning:
        return PolicyDecision(
            decision="warn",
            exit_code=0,
            reason=(
                f"{len(warning)} finding(s) at or above severity "
                f"'{config.warn_on_severity_at_or_above.value}', below the fail threshold."
            ),
            triggered_finding_ids=[f.id for f in warning],
        )

    return PolicyDecision(
        decision="pass",
        exit_code=0,
        reason="No findings at or above the configured warning threshold.",
        triggered_finding_ids=[],
    )
