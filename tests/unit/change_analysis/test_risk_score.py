from infraguard.core.models import Confidence, Finding, Severity
from infraguard.modules.change_analysis.risk_score import compute_risk_score


def _finding(severity: Severity) -> Finding:
    return Finding(
        rule_id="test_rule",
        severity=severity,
        confidence=Confidence.CONFIRMED,
        summary="test",
        detail="test",
    )


def test_no_findings_is_zero() -> None:
    score, explanation = compute_risk_score([])
    assert score == 0
    assert "no findings" in explanation.lower()


def test_score_is_deterministic_and_additive() -> None:
    findings = [_finding(Severity.HIGH), _finding(Severity.HIGH), _finding(Severity.LOW)]
    score, _ = compute_risk_score(findings)
    assert score == 7 + 7 + 1


def test_score_is_capped_at_100() -> None:
    findings = [_finding(Severity.CRITICAL) for _ in range(20)]
    score, explanation = compute_risk_score(findings)
    assert score == 100
    assert "capped" in explanation
