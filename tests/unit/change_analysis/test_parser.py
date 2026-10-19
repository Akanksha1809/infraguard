import pytest

from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.models import ChangeAction
from infraguard.modules.change_analysis.parser import parse_plan


def test_parses_create_action(load_fixture) -> None:
    parsed = parse_plan(load_fixture("create_simple.json"))
    assert len(parsed.resource_changes) == 1
    rc = parsed.resource_changes[0]
    assert rc.address == "aws_s3_bucket.data"
    assert rc.action is ChangeAction.CREATE
    assert rc.after_unknown_paths == ["arn", "id"]


def test_parses_delete_action(load_fixture) -> None:
    parsed = parse_plan(load_fixture("delete_database.json"))
    rc = parsed.resource_changes[0]
    assert rc.action is ChangeAction.DELETE
    assert rc.after is None


def test_parses_replace_destroy_before_create(load_fixture) -> None:
    parsed = parse_plan(load_fixture("replace_destroy_before_create.json"))
    rc = parsed.resource_changes[0]
    assert rc.action is ChangeAction.REPLACE
    assert rc.create_before_destroy is False


def test_parses_replace_create_before_destroy(load_fixture) -> None:
    parsed = parse_plan(load_fixture("replace_create_before_destroy.json"))
    rc = parsed.resource_changes[0]
    assert rc.action is ChangeAction.REPLACE
    assert rc.create_before_destroy is True
    assert rc.replace_paths == ["name"]


def test_parses_no_op_and_read(load_fixture) -> None:
    parsed = parse_plan(load_fixture("no_op_and_read.json"))
    actions = {rc.address: rc.action for rc in parsed.resource_changes}
    assert actions["aws_vpc.main"] is ChangeAction.NO_OP
    assert actions["data.aws_ami.ubuntu"] is ChangeAction.READ
    assert parsed.warnings == []


def test_redacts_sensitive_values_while_parsing(load_fixture) -> None:
    parsed = parse_plan(load_fixture("update_sensitive.json"))
    rc = parsed.resource_changes[0]
    assert rc.after["password"] == "***REDACTED***"
    assert rc.after["api_token"] == "***REDACTED***"  # heuristic, not Terraform-marked
    assert rc.after["instance_class"] == "db.t3.small"
    assert "password" in rc.sensitive_paths
    assert "api_token" in rc.sensitive_paths


def test_flattens_nested_unknown_values(load_fixture) -> None:
    parsed = parse_plan(load_fixture("unknown_values.json"))
    rc = parsed.resource_changes[0]
    assert "id" in rc.after_unknown_paths
    assert "network_interface[0].private_ip" in rc.after_unknown_paths


def test_builds_dependency_edges_from_depends_on_and_references(load_fixture) -> None:
    parsed = parse_plan(load_fixture("dependency_chain.json"))
    edges = set(parsed.dependency_edges)
    assert ("aws_security_group.app", "aws_vpc.main") in edges
    assert ("aws_instance.web", "aws_security_group.app") in edges


def test_module_scoped_resource_produces_warning(load_fixture) -> None:
    parsed = parse_plan(load_fixture("module_scoped.json"))
    codes = {w.code for w in parsed.warnings}
    assert "module_scoped_dependencies_unsupported" in codes


def test_missing_resource_changes_key_is_fatal(load_fixture) -> None:
    with pytest.raises(InputValidationError):
        parse_plan(load_fixture("malformed_missing_resource_changes.json"))


def test_root_not_an_object_is_fatal() -> None:
    with pytest.raises(InputValidationError):
        parse_plan([])


def test_entry_missing_address_is_recoverable_warning(load_fixture) -> None:
    parsed = parse_plan(load_fixture("malformed_entry_missing_address.json"))
    assert parsed.resource_changes == []
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].code == "resource_change_missing_address"


def test_unrecognized_action_combination_warns() -> None:
    raw = {
        "resource_changes": [
            {
                "address": "aws_instance.x",
                "mode": "managed",
                "type": "aws_instance",
                "name": "x",
                "change": {"actions": ["read", "delete"], "before": {}, "after": {}},
            }
        ]
    }
    parsed = parse_plan(raw)
    assert parsed.resource_changes[0].action is ChangeAction.UNKNOWN
    assert any(w.code == "unrecognized_action_combination" for w in parsed.warnings)
