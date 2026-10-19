from infraguard.core.models import Confidence, Finding, PolicyDecision, Report, Severity
from infraguard.core.reporting import render_json, render_markdown


def _sample_report() -> Report:
    return Report(
        module="change_analysis",
        findings=[
            Finding(
                rule_id="destructive_delete",
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                summary="x will be deleted",
                detail="details here",
                affected_resources=["x"],
                remediation="back it up first",
            )
        ],
        assumptions=["assumption one"],
        limitations=["limitation one"],
        policy_decision=PolicyDecision(
            decision="fail", exit_code=1, reason="1 critical finding", triggered_finding_ids=["abc"]
        ),
        next_steps=["review before applying"],
    )


def test_render_json_round_trips() -> None:
    report = _sample_report()
    parsed = Report.model_validate_json(render_json(report))
    assert parsed.run_id == report.run_id
    assert parsed.findings[0].rule_id == "destructive_delete"


def test_render_markdown_contains_key_sections() -> None:
    markdown = render_markdown(_sample_report())
    assert "CRITICAL" in markdown
    assert "destructive_delete" in markdown
    assert "Policy decision" in markdown
    assert "FAIL" in markdown
    assert "Assumptions" in markdown
    assert "Limitations" in markdown
    assert "Recommended next steps" in markdown


def test_render_markdown_handles_no_findings() -> None:
    report = Report(module="change_analysis")
    markdown = render_markdown(report)
    assert "No findings." in markdown
