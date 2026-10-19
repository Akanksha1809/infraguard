"""Turn simulation results and static topology structure into `Finding`s.

Two independent kinds of analysis live here:

- Static analysis (`find_single_points_of_failure`, `find_redundancy_gaps`): properties of
  the topology itself, independent of any specific failure scenario.
- Scenario analysis (`scenario_findings`): what a specific `SimulationResult` means.
"""

from infraguard.core.models import Confidence, Finding, Severity
from infraguard.modules.failure_simulation.capacity import CapacityResult, compute_capacity
from infraguard.modules.failure_simulation.grouping import build_group_membership, group_key
from infraguard.modules.failure_simulation.models import FailureScenario, Topology
from infraguard.modules.failure_simulation.simulator import SimulationResult, simulate


def find_single_points_of_failure(topology: Topology) -> list[Finding]:
    """For every component, simulate failing *only* that one component. If anything else
    goes down as a result, it's a single point of failure. A component with a surviving
    redundant peer never triggers this, because its logical node isn't fully down.
    """
    findings = []
    for component in topology.components:
        scenario = FailureScenario(
            name=f"spof-check:{component.id}", failed_component_ids=[component.id]
        )
        result = simulate(topology, scenario)
        blast = result.down - {component.id}
        if blast:
            findings.append(
                Finding(
                    rule_id="single_point_of_failure",
                    severity=Severity.HIGH,
                    confidence=Confidence.HEURISTIC,
                    summary=f"'{component.id}' is a single point of failure",
                    detail=(
                        f"Simulating only '{component.id}' failing causes {len(blast)} "
                        "other component(s) to go down, per this topology's declared "
                        "dependencies and redundancy groups. This is only as sound as "
                        "those declarations — it is not a measurement of the real system."
                    ),
                    affected_resources=sorted({component.id, *blast}),
                    evidence={"failed": component.id, "cascaded": sorted(blast)},
                    remediation=(
                        f"Give '{component.id}' a redundant peer (same redundancy_group), "
                        "or mark dependents' dependency on it as optional if that's accurate."
                    ),
                )
            )
    return findings


def find_redundancy_gaps(topology: Topology) -> list[Finding]:
    """A required dependency whose target's logical node has exactly one member — nothing
    can take over if that target fails.
    """
    by_id = {c.id: c for c in topology.components}
    groups = build_group_membership(topology)
    findings = []
    flagged_targets: set[str] = set()

    for dep in topology.dependencies:
        if not dep.required or dep.to_id in flagged_targets:
            continue
        target = by_id.get(dep.to_id)
        if target is None:
            continue
        key = group_key(target.id, target.redundancy_group)
        members = groups.get(key, [target.id])
        if len(members) == 1:
            flagged_targets.add(dep.to_id)
            findings.append(
                Finding(
                    rule_id="dependency_without_redundancy",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.CONFIRMED,
                    summary=f"'{dep.to_id}' is a required dependency with no redundancy",
                    detail=(
                        f"'{dep.from_id}' has a required dependency on '{dep.to_id}', which "
                        "declares no redundancy_group peers. This is read directly from the "
                        "topology, not inferred."
                    ),
                    affected_resources=[dep.to_id, dep.from_id],
                    evidence={"target": dep.to_id, "members": members},
                    remediation=(
                        f"Give '{dep.to_id}' a redundant peer, or confirm this dependency "
                        "is genuinely required rather than optional."
                    ),
                )
            )
    return findings


def _capacity_findings(capacity_results: list[CapacityResult]) -> list[Finding]:
    findings = []
    for cap in capacity_results:
        if cap.percent_remaining is None:
            if cap.note and "Incomplete" in cap.note:
                continue  # not an actionable finding on its own; surfaced via report.inputs
            continue
        if 0 < cap.percent_remaining < 100:
            findings.append(
                Finding(
                    rule_id="capacity_degraded",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.CONFIRMED,
                    summary=f"'{cap.label}' is at {cap.percent_remaining}% capacity",
                    detail=(
                        f"Group '{cap.label}' ({', '.join(cap.member_ids)}) has "
                        f"{cap.surviving_capacity} of {cap.total_capacity} declared capacity "
                        "units remaining under this scenario."
                    ),
                    affected_resources=list(cap.member_ids),
                    evidence={
                        "total_capacity": cap.total_capacity,
                        "surviving_capacity": cap.surviving_capacity,
                        "percent_remaining": cap.percent_remaining,
                    },
                    remediation="Confirm remaining capacity is sufficient for expected load.",
                )
            )
    return findings


def scenario_findings(topology: Topology, result: SimulationResult) -> list[Finding]:
    findings = []
    for cid in sorted(result.explicit_failed):
        findings.append(
            Finding(
                rule_id="component_failed_explicit",
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                summary=f"'{cid}' fails in this scenario",
                detail=f"'{cid}' was explicitly failed by this scenario.",
                affected_resources=[cid],
            )
        )
    for cid in sorted(result.cascaded):
        step = result.propagation[cid]
        findings.append(
            Finding(
                rule_id="component_down_cascaded",
                severity=Severity.HIGH,
                confidence=Confidence.HEURISTIC,
                summary=f"'{cid}' goes down as a consequence",
                detail=f"'{cid}' was not directly failed, but goes down due to a {step.reason}.",
                affected_resources=sorted({cid, step.dependency_target}),
                evidence={"dependency_target": step.dependency_target, "reason": step.reason},
                remediation=(
                    f"Add redundancy for '{step.dependency_target}', or confirm '{cid}' "
                    "genuinely cannot tolerate that dependency being unavailable."
                ),
            )
        )

    capacity_results = compute_capacity(topology, result.down)
    findings.extend(_capacity_findings(capacity_results))
    return findings
