import pytest

from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.analyzer import analyze_plan_file
from infraguard.modules.change_analysis.policy import PolicyConfig


def test_analyze_plan_file_end_to_end(fixture_path) -> None:
    report = analyze_plan_file(fixture_path("delete_database.json"))

    assert report.module == "change_analysis"
    assert report.policy_decision is not None
    assert report.policy_decision.decision == "fail"  # CRITICAL delete trips the default HIGH threshold
    assert report.inputs["resource_change_count"] == 1
    assert "risk_score" in report.inputs


def test_strict_policy_errors_on_parse_warning(fixture_path) -> None:
    report = analyze_plan_file(fixture_path("malformed_entry_missing_address.json"))
    assert report.policy_decision.decision == "error"
    assert report.policy_decision.exit_code == 2


def test_lenient_policy_passes_clean_plan(fixture_path) -> None:
    report = analyze_plan_file(fixture_path("no_op_and_read.json"), PolicyConfig())
    assert report.policy_decision.decision == "pass"
    assert report.policy_decision.exit_code == 0


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(InputValidationError):
        analyze_plan_file(tmp_path / "does-not-exist.json")


def test_invalid_json_syntax_raises(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        analyze_plan_file(fixture_path("invalid_json_syntax.json"))


def test_rendered_report_never_contains_a_raw_secret_value(fixture_path) -> None:
    from infraguard.core.reporting import render_json, render_markdown

    report = analyze_plan_file(fixture_path("delete_with_secret.json"))

    for rendered in (render_json(report), render_markdown(report)):
        assert "super-secret-value" not in rendered
        assert "unmarked-token-value" not in rendered
        assert "***REDACTED***" in rendered  # the redaction is actually visible, not just absent


def test_oversized_file_rejected(tmp_path) -> None:
    import infraguard.modules.change_analysis.analyzer as analyzer_module

    big_file = tmp_path / "big.json"
    big_file.write_text("{}")
    original_max = analyzer_module.MAX_PLAN_SIZE_BYTES
    analyzer_module.MAX_PLAN_SIZE_BYTES = 1  # force the size check to trip
    try:
        with pytest.raises(InputValidationError):
            analyze_plan_file(big_file)
    finally:
        analyzer_module.MAX_PLAN_SIZE_BYTES = original_max
