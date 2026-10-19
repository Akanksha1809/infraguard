"""Redundancy-group membership helpers.

A "logical node" is a redundancy_group if the component declares one, otherwise the
component itself (a singleton group of one). This single concept is what both the
simulator (is this logical node fully down?) and the static redundancy-gap check (does this
dependency target have more than one member?) are built on.
"""

from infraguard.modules.failure_simulation.models import Topology


def group_key(component_id: str, redundancy_group: str | None) -> str:
    return f"group::{redundancy_group}" if redundancy_group else f"singleton::{component_id}"


def build_group_membership(topology: Topology) -> dict[str, list[str]]:
    """Group key -> member component ids, in declaration order."""
    groups: dict[str, list[str]] = {}
    for component in topology.components:
        key = group_key(component.id, component.redundancy_group)
        groups.setdefault(key, []).append(component.id)
    return groups


def group_key_by_component_id(topology: Topology) -> dict[str, str]:
    """Component id -> its logical node's group key."""
    return {c.id: group_key(c.id, c.redundancy_group) for c in topology.components}


def group_members_of(topology: Topology, component_id: str) -> list[str]:
    key_by_id = group_key_by_component_id(topology)
    if component_id not in key_by_id:
        return [component_id]
    target_key = key_by_id[component_id]
    groups = build_group_membership(topology)
    return groups.get(target_key, [component_id])
