from infraguard.modules.failure_simulation.grouping import (
    build_group_membership,
    group_members_of,
)
from infraguard.modules.failure_simulation.validator import parse_topology


def test_singleton_component_is_its_own_group(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("simple_chain.yaml"))
    assert group_members_of(topology, "a") == ["a"]


def test_redundancy_group_members_grouped_together(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    members = group_members_of(topology, "app-1")
    assert set(members) == {"app-1", "app-2"}


def test_build_group_membership_covers_all_components(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    groups = build_group_membership(topology)
    all_members = {m for members in groups.values() for m in members}
    assert all_members == {"client", "lb", "app-1", "app-2"}
