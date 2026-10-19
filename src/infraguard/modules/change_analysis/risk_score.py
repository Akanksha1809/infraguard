"""A deterministic, explained risk score. Purely informational: policy decisions (policy.py)
are driven by explicit severity thresholds over findings, never by this aggregate number —
per the project constraint that a numeric score must never itself approve or reject a change.
"""

from collections import Counter

from infraguard.core.models import Finding, Severity

_WEIGHTS: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 3,
    Severity.HIGH: 7,
    Severity.CRITICAL: 15,
}
_MAX_SCORE = 100


def compute_risk_score(findings: list[Finding]) -> tuple[int, str]:
    counts = Counter(f.severity for f in findings)
    raw_total = sum(_WEIGHTS[severity] * count for severity, count in counts.items())
    score = min(raw_total, _MAX_SCORE)

    if not findings:
        return 0, "score = 0; no findings."

    contributions = ", ".join(
        f"{counts[s]}×{s.value.upper()} (weight {_WEIGHTS[s]})"
        for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)
        if counts[s]
    )
    cap_note = f" (raw total {raw_total}, capped at {_MAX_SCORE})" if raw_total > _MAX_SCORE else ""
    explanation = (
        f"score = {score}{cap_note}; contributions: {contributions}. "
        "Informational only — see the policy decision for the pass/fail determination."
    )
    return score, explanation
