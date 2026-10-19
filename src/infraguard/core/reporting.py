"""Render a shared `Report` as JSON or Markdown. One renderer, used by every module, so
report structure and tone stay consistent regardless of which module produced it.
"""

from infraguard.core.models import Report, Severity

_SEVERITY_LABEL = {
    Severity.CRITICAL: "CRITICAL",
    Severity.HIGH: "HIGH",
    Severity.MEDIUM: "MEDIUM",
    Severity.LOW: "LOW",
}


def render_json(report: Report) -> str:
    return report.model_dump_json(indent=2)


def render_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"# InfraGuard Report — {report.module}")
    lines.append("")
    lines.append(f"- **Run ID:** `{report.run_id}`")
    lines.append(f"- **Created:** {report.created_at.isoformat()}")
    lines.append(f"- **Schema version:** {report.schema_version}")
    lines.append("")

    if report.policy_decision:
        pd = report.policy_decision
        lines.append("## Policy decision")
        lines.append("")
        lines.append(f"- **Decision:** `{pd.decision.upper()}` (exit code {pd.exit_code})")
        lines.append(f"- **Reason:** {pd.reason}")
        if pd.triggered_finding_ids:
            lines.append(f"- **Triggered by findings:** {', '.join(pd.triggered_finding_ids)}")
        lines.append("")

    lines.append(f"## Findings ({len(report.findings)})")
    lines.append("")
    if not report.findings:
        lines.append("No findings.")
    else:
        by_severity = sorted(report.findings, key=lambda f: f.severity.rank, reverse=True)
        for finding in by_severity:
            lines.append(
                f"### [{_SEVERITY_LABEL[finding.severity]}] {finding.summary} "
                f"(`{finding.rule_id}`, confidence: {finding.confidence.value})"
            )
            lines.append("")
            lines.append(finding.detail)
            lines.append("")
            if finding.affected_resources:
                lines.append(f"- **Affected resources:** {', '.join(finding.affected_resources)}")
            if finding.evidence:
                lines.append(f"- **Evidence:** `{finding.evidence}`")
            if finding.remediation:
                lines.append(f"- **Remediation:** {finding.remediation}")
            lines.append("")
    lines.append("")

    if report.assumptions:
        lines.append("## Assumptions")
        lines.append("")
        lines.extend(f"- {a}" for a in report.assumptions)
        lines.append("")

    if report.limitations:
        lines.append("## Limitations")
        lines.append("")
        lines.extend(f"- {lim}" for lim in report.limitations)
        lines.append("")

    if report.next_steps:
        lines.append("## Recommended next steps")
        lines.append("")
        lines.extend(f"- {s}" for s in report.next_steps)
        lines.append("")

    return "\n".join(lines)
