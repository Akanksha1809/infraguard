from infraguard.core.graph import build_graph
from infraguard.core.models import Severity
from infraguard.modules.change_analysis.parser import parse_plan
from infraguard.modules.change_analysis.rules import run_rules


def _run(load_fixture, name: str):
    parsed = parse_plan(load_fixture(name))
    graph = build_graph([rc.address for rc in parsed.resource_changes], parsed.dependency_edges)
    return run_rules(parsed, graph)


def test_delete_database_is_critical(load_fixture) -> None:
    findings = _run(load_fixture, "delete_database.json")
    destructive = [f for f in findings if f.rule_id == "destructive_delete"]
    assert len(destructive) == 1
    assert destructive[0].severity is Severity.CRITICAL
    assert destructive[0].confidence.value == "confirmed"


def test_replace_without_replace_paths_notes_incomplete_info(load_fixture) -> None:
    findings = _run(load_fixture, "replace_destroy_before_create.json")
    replace_findings = [f for f in findings if f.rule_id == "destructive_replace"]
    assert len(replace_findings) == 1
    assert "did not report which attribute" in replace_findings[0].detail


def test_replace_with_replace_paths_cites_them(load_fixture) -> None:
    findings = _run(load_fixture, "replace_create_before_destroy.json")
    replace_findings = [f for f in findings if f.rule_id == "destructive_replace"]
    assert "name" in replace_findings[0].detail


def test_no_op_and_read_produce_no_destructive_findings(load_fixture) -> None:
    findings = _run(load_fixture, "no_op_and_read.json")
    assert not any(f.rule_id in ("destructive_delete", "destructive_replace") for f in findings)


def test_unknown_values_flagged(load_fixture) -> None:
    findings = _run(load_fixture, "unknown_values.json")
    unknown_findings = [f for f in findings if f.rule_id == "unknown_after_values"]
    assert len(unknown_findings) == 1
    assert unknown_findings[0].evidence["unknown_path_count"] == 2


def test_unsupported_resource_type_flagged_alongside_destructive(load_fixture) -> None:
    findings = _run(load_fixture, "unsupported_resource_type.json")
    rule_ids = {f.rule_id for f in findings}
    assert "unsupported_resource_type" in rule_ids
    assert "destructive_delete" in rule_ids


def test_dependents_affected_lists_both_direct_and_transitive(load_fixture) -> None:
    findings = _run(load_fixture, "dependency_chain.json")
    dependents_findings = [f for f in findings if f.rule_id == "dependents_affected"]
    assert len(dependents_findings) == 1
    affected = set(dependents_findings[0].affected_resources)
    assert affected == {"aws_security_group.app", "aws_instance.web"}


def test_module_scoped_warning_becomes_finding(load_fixture) -> None:
    findings = _run(load_fixture, "module_scoped.json")
    assert any(f.rule_id == "parse_warning.module_scoped_dependencies_unsupported" for f in findings)


def test_sensitive_category_mutation_on_update(load_fixture) -> None:
    findings = _run(load_fixture, "update_sensitive.json")
    assert any(f.rule_id == "sensitive_category_mutation" for f in findings)


def test_destructive_delete_evidence_includes_redacted_before(load_fixture) -> None:
    findings = _run(load_fixture, "delete_with_secret.json")
    finding = next(f for f in findings if f.rule_id == "destructive_delete")

    before = finding.evidence["before"]
    assert before["master_password"] == "***REDACTED***"  # Terraform-marked sensitive
    assert before["api_token"] == "***REDACTED***"  # heuristic key-name match
    assert before["instance_class"] == "db.t3.micro"  # non-sensitive value passes through


def test_destructive_replace_evidence_includes_redacted_before_and_after(load_fixture) -> None:
    findings = _run(load_fixture, "replace_with_secret.json")
    finding = next(f for f in findings if f.rule_id == "destructive_replace")

    assert finding.evidence["before"]["master_password"] == "***REDACTED***"
    assert finding.evidence["after"]["master_password"] == "***REDACTED***"
    assert finding.evidence["before"]["api_token"] == "***REDACTED***"
    assert finding.evidence["before"]["engine_version"] == "14.9"
    assert finding.evidence["after"]["engine_version"] == "16.4"
