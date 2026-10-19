"""Surviving-capacity calculation, only where every member of a logical node declares a
capacity. A missing capacity value is never treated as zero or as "healthy" — it is
reported as genuinely unknown, per the project rule that absent data never implies safety
(or, here, implies risk either — it simply means no ratio can be honestly computed).
"""

from dataclasses import dataclass

from infraguard.modules.failure_simulation.grouping import build_group_membership
from infraguard.modules.failure_simulation.models import Topology


@dataclass
class CapacityResult:
    group_key: str
    label: str
    member_ids: list[str]
    total_capacity: float | None
    surviving_capacity: float | None
    percent_remaining: float | None
    note: str | None = None


def compute_capacity(topology: Topology, down: set[str]) -> list[CapacityResult]:
    by_id = {c.id: c for c in topology.components}
    groups = build_group_membership(topology)
    results: list[CapacityResult] = []

    for key, member_ids in groups.items():
        members = [by_id[m] for m in member_ids]
        label = members[0].redundancy_group or members[0].id
        capacities = [m.capacity for m in members]

        if any(c is None for c in capacities):
            results.append(
                CapacityResult(
                    group_key=key,
                    label=label,
                    member_ids=member_ids,
                    total_capacity=None,
                    surviving_capacity=None,
                    percent_remaining=None,
                    note=(
                        "Incomplete capacity data: at least one member has no declared "
                        "'capacity', so a surviving-capacity ratio cannot be honestly "
                        "computed for this group."
                    ),
                )
            )
            continue

        total = sum(capacities)  # type: ignore[arg-type]
        surviving = sum(c for c, m in zip(capacities, members, strict=True) if m.id not in down)  # type: ignore[misc]
        if total > 0:
            percent = round(surviving / total * 100, 1)
            note = None
        else:
            percent = None
            note = "Total declared capacity is zero; a percentage is undefined."

        results.append(
            CapacityResult(
                group_key=key,
                label=label,
                member_ids=member_ids,
                total_capacity=total,
                surviving_capacity=surviving,
                percent_remaining=percent,
                note=note,
            )
        )

    return results
