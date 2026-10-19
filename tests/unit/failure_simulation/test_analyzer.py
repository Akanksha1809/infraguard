import pytest

from infraguard.errors import InputValidationError
from infraguard.modules.failure_simulation.analyzer import (
    simulate_failure_file,
    validate_topology_file,
)
from infraguard.modules.failure_simulation.models import FailureScenario


def test_validate_topology_file_end_to_end(fixture_path) -> None:
    report = validate_topology_file(fixture_path("simple_chain.yaml"))
    assert report.module == "failure_simulation"
    assert report.inputs["component_count"] == 3
    assert report.inputs["dependency_count"] == 2
    assert "graph" in report.inputs
    assert len(report.inputs["graph"]["nodes"]) == 3


def test_validate_topology_file_missing_raises(tmp_path) -> None:
    with pytest.raises(InputValidationError):
        validate_topology_file(tmp_path / "missing.yaml")


def test_validate_topology_file_fatal_error_raises(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        validate_topology_file(fixture_path("duplicate_ids.yaml"))


def test_validate_topology_file_invalid_yaml_raises(fixture_path) -> None:
    with pytest.raises(InputValidationError):
        validate_topology_file(fixture_path("invalid_yaml_syntax.yaml"))


def test_simulate_failure_file_end_to_end(fixture_path) -> None:
    report = simulate_failure_file(
        fixture_path("simple_chain.yaml"), FailureScenario(failed_component_ids=["c"])
    )
    assert report.inputs["explicit_failed"] == ["c"]
    assert report.inputs["cascaded"] == ["a", "b"]
    assert any(f.rule_id == "single_point_of_failure" for f in report.findings)


def test_simulate_failure_on_example_topology_shows_no_cascade(example_path) -> None:
    report = simulate_failure_file(
        example_path("multi-zone-redundant.yaml"),
        FailureScenario(failed_domains=["zone-a"]),
    )
    assert report.inputs["cascaded"] == []
    assert not any(f.rule_id == "single_point_of_failure" for f in report.findings)


def test_simulate_failure_on_fragile_example_cascades_fully(example_path) -> None:
    report = simulate_failure_file(
        example_path("fragile-single-instance.yaml"),
        FailureScenario(failed_component_ids=["app"]),
    )
    assert set(report.inputs["cascaded"]) == {"client", "lb"}


def test_simulate_failure_on_shared_db_bottleneck(example_path) -> None:
    report = simulate_failure_file(
        example_path("redundant-app-shared-db-bottleneck.yaml"),
        FailureScenario(failed_component_ids=["db"]),
    )
    assert set(report.inputs["cascaded"]) == {"app-1", "app-2", "lb", "client"}
