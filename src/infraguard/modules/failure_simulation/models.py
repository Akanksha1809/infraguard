"""Topology and failure-scenario models.

Semantics are defined precisely in docs/FAILURE_SIMULATION.md — this module intentionally
does not claim to model network partitions, correlated failures, or real-world probability.
It models exactly one thing: whether a declared component is reachable/functional given a
declared set of required dependencies and declared redundancy groupings.
"""

from pydantic import BaseModel, Field, model_validator


class Component(BaseModel):
    id: str
    name: str
    kind: str
    failure_domain: str | None = None
    capacity: float | None = None
    """Arbitrary units (e.g. requests/sec). Only meaningful relative to other components in
    the same redundancy_group — comparing capacity across groups is not meaningful."""
    redundancy_group: str | None = None
    """Components sharing a redundancy_group are treated as interchangeable peers serving
    the same role. A group is considered down only when ALL of its members are down."""


class Dependency(BaseModel):
    from_id: str
    to_id: str
    required: bool = True
    """A required dependency propagates failure: if the target's entire redundancy group is
    down, the dependent is also considered down. An optional dependency never propagates
    failure — it is noted as degraded in reports, but does not cascade."""

    @model_validator(mode="after")
    def _no_self_loop(self) -> "Dependency":
        if self.from_id == self.to_id:
            raise ValueError(f"Dependency '{self.from_id}' cannot depend on itself.")
        return self


class Topology(BaseModel):
    name: str
    description: str | None = None
    components: list[Component] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)


class TopologyWarning(BaseModel):
    code: str
    message: str


class FailureScenario(BaseModel):
    name: str = "unnamed scenario"
    failed_component_ids: list[str] = Field(default_factory=list)
    failed_domains: list[str] = Field(default_factory=list)
