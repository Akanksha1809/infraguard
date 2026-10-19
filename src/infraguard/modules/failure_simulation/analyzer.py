"""Entry points tying parsing, the simulator, and analysis together into `Report`s — the
only functions the CLI and API call.
"""

from pathlib import Path
from typing import Any

import yaml

from infraguard.core.models import Confidence, Finding, Report, Severity
from infraguard.errors import InputValidationError
from infraguard.modules.failure_simulation.analysis import (
    find_redundancy_gaps,
    find_single_points_of_failure,
    scenario_findings,
)
from infraguard.modules.failure_simulation.capacity import compute_capacity
from infraguard.modules.failure_simulation.models import FailureScenario, Topology, TopologyWarning
from infraguard.modules.failure_simulation.simulator import simulate
from infraguard.modules.failure_simulation.validator import parse_topology

MAX_TOPOLOGY_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB; a hand-authored topology is never this large.

_ASSUMPTIONS = [
    "A component is 'down' only if explicitly failed, or if ALL members of a required "
    "dependency's redundancy group are down — there is no partial-capability model.",
    "Redundant peers (same redundancy_group) are treated as fully interchangeable: which "
    "specific peer actually serves a request is not modeled.",
    "An optional (required: false) dependency never propagates failure.",
]
_LIMITATIONS = [
    "This is a structural model of declared dependencies, not a measurement of a real "
    "system: no network partitions, no correlated failures, no provider SLAs.",
    "No availability percentage (e.g. '99.99%') is claimed anywhere — only what the "
    "declared topology and failure scenario imply structurally.",
    "Surviving-capacity ratios are only computed for a redundancy group where every "
    "member declares a 'capacity' value; otherwise it is reported as unknown, not assumed.",
]


def _warning_findings(warnings: list[TopologyWarning]) -> list[Finding]:
    return [
        Finding(
            rule_id=f"topology_warning.{w.code}",
            severity=Severity.LOW if w.code != "dependency_cycle" else Severity.MEDIUM,
            confidence=Confidence.CONFIRMED,
            summary=f"Topology warning: {w.code}",
            detail=w.message,
        )
        for w in warnings
    ]


def _dependency_graph_view(topology: Topology) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": c.id,
                "name": c.name,
                "kind": c.kind,
                "failure_domain": c.failure_domain,
                "redundancy_group": c.redundancy_group,
                "capacity": c.capacity,
            }
            for c in topology.components
        ],
        "edges": [
            {"from": d.from_id, "to": d.to_id, "required": d.required}
            for d in topology.dependencies
        ],
    }


def _load_topology_document(path: Path) -> Any:
    if not path.exists():
        raise InputValidationError(f"Topology file not found: {path}")
    size = path.stat().st_size
    if size > MAX_TOPOLOGY_SIZE_BYTES:
        raise InputValidationError(
            f"Topology file '{path}' is {size} bytes, exceeding the "
            f"{MAX_TOPOLOGY_SIZE_BYTES}-byte limit.",
            details={"size_bytes": size, "max_bytes": MAX_TOPOLOGY_SIZE_BYTES},
        )
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise InputValidationError(f"Topology file '{path}' is not valid YAML/JSON: {exc}") from exc


def validate_topology(raw: Any, *, source: str | None = None) -> Report:
    topology, warnings = parse_topology(raw)
    findings = _warning_findings(warnings)

    return Report(
        module="failure_simulation",
        inputs={
            "source": source,
            "topology_name": topology.name,
            "component_count": len(topology.components),
            "dependency_count": len(topology.dependencies),
            "graph": _dependency_graph_view(topology),
        },
        findings=findings,
        assumptions=_ASSUMPTIONS,
        limitations=_LIMITATIONS,
        next_steps=["Run 'simulate-failure' to evaluate specific failure scenarios."],
    )


def validate_topology_file(path: Path) -> Report:
    raw = _load_topology_document(path)
    return validate_topology(raw, source=str(path))


def simulate_failure(raw: Any, scenario: FailureScenario, *, source: str | None = None) -> Report:
    topology, warnings = parse_topology(raw)
    result = simulate(topology, scenario)

    findings = _warning_findings(warnings)
    findings.extend(find_single_points_of_failure(topology))
    findings.extend(find_redundancy_gaps(topology))
    findings.extend(scenario_findings(topology, result))

    baseline_capacity = compute_capacity(topology, down=set())
    scenario_capacity = compute_capacity(topology, down=result.down)

    next_steps = ["Review HIGH-severity findings and any SPOF before relying on this topology."]
    if result.cascaded:
        next_steps.insert(
            0,
            f"{len(result.cascaded)} component(s) go down as a consequence of this "
            "scenario, not directly — trace each via its finding's evidence.",
        )

    return Report(
        module="failure_simulation",
        inputs={
            "source": source,
            "topology_name": topology.name,
            "scenario": scenario.model_dump(mode="json"),
            "explicit_failed": sorted(result.explicit_failed),
            "cascaded": sorted(result.cascaded),
            "total_down": sorted(result.down),
            "graph": _dependency_graph_view(topology),
            "baseline_capacity": [
                {
                    "label": c.label,
                    "member_ids": c.member_ids,
                    "total_capacity": c.total_capacity,
                    "percent_remaining": c.percent_remaining,
                }
                for c in baseline_capacity
            ],
            "scenario_capacity": [
                {
                    "label": c.label,
                    "member_ids": c.member_ids,
                    "total_capacity": c.total_capacity,
                    "surviving_capacity": c.surviving_capacity,
                    "percent_remaining": c.percent_remaining,
                    "note": c.note,
                }
                for c in scenario_capacity
            ],
        },
        findings=findings,
        assumptions=_ASSUMPTIONS,
        limitations=_LIMITATIONS,
        next_steps=next_steps,
    )


def simulate_failure_file(path: Path, scenario: FailureScenario) -> Report:
    raw = _load_topology_document(path)
    return simulate_failure(raw, scenario, source=str(path))
