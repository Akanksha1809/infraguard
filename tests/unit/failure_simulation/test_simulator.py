from infraguard.modules.failure_simulation.models import FailureScenario
from infraguard.modules.failure_simulation.simulator import simulate
from infraguard.modules.failure_simulation.validator import parse_topology


def test_cascades_through_simple_chain(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["c"]))
    assert result.explicit_failed == {"c"}
    assert result.cascaded == {"a", "b"}
    assert result.down == {"a", "b", "c"}
    assert result.propagation["b"].dependency_target == "c"
    assert result.propagation["a"].dependency_target == "b"


def test_optional_dependency_does_not_cascade(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("optional_dependency.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["cache"]))
    assert result.cascaded == set()
    assert result.down == {"cache"}


def test_redundant_peer_survives_single_failure(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["app-1"]))
    assert "app-2" not in result.down
    assert "lb" not in result.down  # lb's dependency on the 'app' group is still satisfied


def test_failing_entire_redundancy_group_cascades(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["app-1", "app-2"]))
    assert result.cascaded == {"lb", "client"}


def test_failure_domain_resolves_to_member_components() -> None:
    raw = {
        "name": "domain-test",
        "components": [
            {"id": "a", "name": "A", "kind": "service", "failure_domain": "zone-a"},
            {"id": "b", "name": "B", "kind": "service", "failure_domain": "zone-b"},
        ],
        "dependencies": [],
    }
    topology, _ = parse_topology(raw)
    result = simulate(topology, FailureScenario(failed_domains=["zone-a"]))
    assert result.explicit_failed == {"a"}


def test_unknown_component_id_in_scenario_is_ignored_not_crashing(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["does-not-exist"]))
    assert result.explicit_failed == set()
    assert result.down == set()


def test_no_op_scenario_leaves_everything_up(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    result = simulate(topology, FailureScenario())
    assert result.down == set()
