"""The cascading-failure propagation engine.

A component is down if it was explicitly failed, OR if it has at least one `required`
dependency whose target's entire redundancy group is down. This is computed as a monotonic
fixed point: once a component is marked down it stays down, so propagation always
terminates in at most `len(components)` passes. See docs/FAILURE_SIMULATION.md for the full
semantics and their stated limitations.
"""

from dataclasses import dataclass, field

from infraguard.modules.failure_simulation.grouping import (
    build_group_membership,
    group_key_by_component_id,
)
from infraguard.modules.failure_simulation.models import FailureScenario, Topology


@dataclass
class PropagationStep:
    component_id: str
    dependency_target: str
    reason: str


@dataclass
class SimulationResult:
    explicit_failed: set[str]
    down: set[str]
    cascaded: set[str]
    propagation: dict[str, PropagationStep] = field(default_factory=dict)


def resolve_explicit_failures(topology: Topology, scenario: FailureScenario) -> set[str]:
    known_ids = {c.id for c in topology.components}
    failed = {cid for cid in scenario.failed_component_ids if cid in known_ids}
    for component in topology.components:
        if component.failure_domain and component.failure_domain in scenario.failed_domains:
            failed.add(component.id)
    return failed


def simulate(topology: Topology, scenario: FailureScenario) -> SimulationResult:
    explicit = resolve_explicit_failures(topology, scenario)
    groups = build_group_membership(topology)
    group_key_by_id = group_key_by_component_id(topology)

    required_targets_by_source: dict[str, list[str]] = {}
    for dep in topology.dependencies:
        if dep.required:
            required_targets_by_source.setdefault(dep.from_id, []).append(dep.to_id)

    down = set(explicit)
    propagation: dict[str, PropagationStep] = {}

    changed = True
    while changed:
        changed = False
        for component in topology.components:
            if component.id in down:
                continue
            for target_id in required_targets_by_source.get(component.id, []):
                target_key = group_key_by_id.get(target_id)
                members = groups.get(target_key, [target_id])
                if members and all(m in down for m in members):
                    down.add(component.id)
                    propagation[component.id] = PropagationStep(
                        component_id=component.id,
                        dependency_target=target_id,
                        reason=(
                            f"required dependency on '{target_id}', whose redundancy "
                            f"group ({', '.join(members)}) is entirely down"
                        ),
                    )
                    changed = True
                    break

    return SimulationResult(
        explicit_failed=explicit, down=down, cascaded=down - explicit, propagation=propagation
    )
