"""Parse and validate a topology document.

Fatal problems (not an object, duplicate component ids, a dependency referencing an unknown
component, a self-referential dependency) raise `InputValidationError` — there is no sound
graph to analyze. A dependency cycle is not fatal (the simulator's fixed-point propagation
handles it correctly) but is reported as a `TopologyWarning` so it isn't silently invisible.
"""

from typing import Any

import networkx as nx
from pydantic import ValidationError

from infraguard.errors import InputValidationError
from infraguard.modules.failure_simulation.models import Topology, TopologyWarning


def parse_topology(raw: Any) -> tuple[Topology, list[TopologyWarning]]:
    if not isinstance(raw, dict):
        raise InputValidationError("Topology document root must be an object.")

    try:
        topology = Topology.model_validate(raw)
    except ValidationError as exc:
        raise InputValidationError(f"Topology document failed validation: {exc}") from exc

    component_ids = [c.id for c in topology.components]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for cid in component_ids:
        if cid in seen:
            duplicates.add(cid)
        seen.add(cid)
    if duplicates:
        raise InputValidationError(
            f"Duplicate component id(s): {sorted(duplicates)}.",
            details={"duplicate_ids": sorted(duplicates)},
        )

    known_ids = set(component_ids)
    unknown_refs: list[str] = []
    for dep in topology.dependencies:
        if dep.from_id not in known_ids:
            unknown_refs.append(dep.from_id)
        if dep.to_id not in known_ids:
            unknown_refs.append(dep.to_id)
    if unknown_refs:
        raise InputValidationError(
            f"Dependencies reference unknown component id(s): {sorted(set(unknown_refs))}.",
            details={"unknown_ids": sorted(set(unknown_refs))},
        )

    warnings: list[TopologyWarning] = []
    graph = nx.DiGraph()
    graph.add_nodes_from(known_ids)
    graph.add_edges_from((dep.from_id, dep.to_id) for dep in topology.dependencies)
    cycles = list(nx.simple_cycles(graph))
    if cycles:
        warnings.append(
            TopologyWarning(
                code="dependency_cycle",
                message=(
                    f"The dependency graph contains {len(cycles)} cycle(s), e.g. "
                    f"{' -> '.join(cycles[0] + [cycles[0][0]])}. Propagation still computes "
                    "correctly (fixed-point), but a cyclic dependency is unusual and worth "
                    "double-checking against the real system."
                ),
            )
        )

    domains = {c.failure_domain for c in topology.components if c.failure_domain}
    referenced_groups = {c.redundancy_group for c in topology.components if c.redundancy_group}
    for group in referenced_groups:
        members = [c for c in topology.components if c.redundancy_group == group]
        if len(members) == 1:
            warnings.append(
                TopologyWarning(
                    code="single_member_redundancy_group",
                    message=(
                        f"redundancy_group '{group}' has only one member "
                        f"('{members[0].id}') — it provides no actual redundancy."
                    ),
                )
            )

    if not domains:
        warnings.append(
            TopologyWarning(
                code="no_failure_domains_declared",
                message=(
                    "No component declares a failure_domain, so domain-level failure "
                    "scenarios (--failure-domain) have nothing to target."
                ),
            )
        )

    return topology, warnings
