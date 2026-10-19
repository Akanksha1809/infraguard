from infraguard.modules.failure_simulation.analysis import (
    find_redundancy_gaps,
    find_single_points_of_failure,
    scenario_findings,
)
from infraguard.modules.failure_simulation.models import FailureScenario
from infraguard.modules.failure_simulation.simulator import simulate
from infraguard.modules.failure_simulation.validator import parse_topology


def test_singleton_chain_components_with_dependents_are_spofs(load_fixture) -> None:
    # a -> b -> c (a depends on b, b depends on c). Failing "a" alone affects nothing else,
    # since nothing depends on "a" — it is the top of the chain, not a SPOF for anyone.
    # "b" and "c" each have a dependent and no redundancy, so both are SPOFs.
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    spofs = {f.evidence["failed"] for f in find_single_points_of_failure(topology)}
    assert spofs == {"b", "c"}
    assert "a" not in spofs


def test_redundant_pair_app_instances_are_not_spofs(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    spofs = {f.evidence["failed"] for f in find_single_points_of_failure(topology)}
    assert "app-1" not in spofs
    assert "app-2" not in spofs
    assert "lb" in spofs  # lb itself still has no redundancy


def test_redundancy_gap_flagged_for_singleton_dependency_target(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    gaps = {f.evidence["target"] for f in find_redundancy_gaps(topology)}
    assert "b" in gaps
    assert "c" in gaps


def test_no_redundancy_gap_for_redundant_target(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    gaps = {f.evidence["target"] for f in find_redundancy_gaps(topology)}
    assert "app-1" not in gaps
    assert "app-2" not in gaps


def test_scenario_findings_include_explicit_and_cascaded(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["c"]))
    findings = scenario_findings(topology, result)
    rule_ids = {f.rule_id for f in findings}
    assert "component_failed_explicit" in rule_ids
    assert "component_down_cascaded" in rule_ids


def test_scenario_findings_include_capacity_degradation(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    result = simulate(topology, FailureScenario(failed_component_ids=["app-1"]))
    findings = scenario_findings(topology, result)
    assert any(f.rule_id == "capacity_degraded" for f in findings)
