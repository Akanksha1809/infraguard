import pytest

from infraguard.errors import InputValidationError
from infraguard.modules.failure_simulation.validator import parse_topology


def test_parses_simple_chain(load_fixture) -> None:
    topology, warnings = parse_topology(load_fixture("simple_chain.yaml"))
    assert len(topology.components) == 3
    assert len(topology.dependencies) == 2
    # simple_chain declares no failure_domain, so a 'no_failure_domains_declared' warning
    # is expected here (see test_no_failure_domains_warns) and no other warning fires.
    assert [w.code for w in warnings] == ["no_failure_domains_declared"]


def test_duplicate_ids_are_fatal(load_fixture) -> None:
    with pytest.raises(InputValidationError):
        parse_topology(load_fixture("duplicate_ids.yaml"))


def test_unknown_reference_is_fatal(load_fixture) -> None:
    with pytest.raises(InputValidationError):
        parse_topology(load_fixture("unknown_reference.yaml"))


def test_self_loop_dependency_is_fatal() -> None:
    raw = {
        "name": "self-loop",
        "components": [{"id": "a", "name": "A", "kind": "service"}],
        "dependencies": [{"from_id": "a", "to_id": "a", "required": True}],
    }
    with pytest.raises(InputValidationError):
        parse_topology(raw)


def test_root_not_an_object_is_fatal(load_fixture) -> None:
    with pytest.raises(InputValidationError):
        parse_topology(load_fixture("not_an_object.yaml"))


def test_cycle_produces_warning_not_error(load_fixture) -> None:
    topology, warnings = parse_topology(load_fixture("cyclic.yaml"))
    assert topology is not None
    assert any(w.code == "dependency_cycle" for w in warnings)


def test_single_member_redundancy_group_warns() -> None:
    raw = {
        "name": "lonely-group",
        "components": [{"id": "a", "name": "A", "kind": "service", "redundancy_group": "solo"}],
        "dependencies": [],
    }
    _, warnings = parse_topology(raw)
    assert any(w.code == "single_member_redundancy_group" for w in warnings)


def test_no_failure_domains_warns(load_fixture) -> None:
    _, warnings = parse_topology(load_fixture("simple_chain.yaml"))
    assert any(w.code == "no_failure_domains_declared" for w in warnings)


def test_multi_zone_example_has_no_warnings(load_example) -> None:
    _, warnings = parse_topology(load_example("multi-zone-redundant.yaml"))
    assert warnings == []
