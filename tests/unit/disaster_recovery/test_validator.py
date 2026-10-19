import pytest
import yaml

from infraguard.errors import InputValidationError
from infraguard.modules.disaster_recovery.validator import (
    parse_evidence_document,
    parse_policy_document,
)


def _load(path):
    return yaml.safe_load(path.read_text())


def test_parses_valid_policy(fixture_path) -> None:
    doc = parse_policy_document(_load(fixture_path("policy_valid.yaml")))
    assert len(doc.policies) == 1
    assert doc.policies[0].workload_id == "wl"


def test_parses_valid_evidence(fixture_path) -> None:
    doc = parse_evidence_document(_load(fixture_path("evidence_valid.json")))
    assert len(doc.backups) == 2
    assert len(doc.drills) == 1


def test_duplicate_workload_id_is_fatal(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        parse_policy_document(_load(fixture_path("policy_duplicate.yaml")))


def test_policy_root_not_object_is_fatal(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        parse_policy_document(_load(fixture_path("policy_not_object.yaml")))


def test_invalid_schema_is_fatal(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        parse_policy_document(_load(fixture_path("policy_invalid_schema.yaml")))


def test_evidence_root_not_object_is_fatal() -> None:
    with pytest.raises(InputValidationError):
        parse_evidence_document([])
