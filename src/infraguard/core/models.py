"""Shared models used by every module: findings, policy decisions, and reports.

Centralizing these here means Change Analysis, Failure Simulation, and Disaster Recovery
all produce the same report shape, and a reviewer only has to learn one vocabulary
(severity, confidence, finding, policy decision) instead of three.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    def __ge__(self, other: str) -> bool:
        return self.rank >= Severity(other).rank

    def __gt__(self, other: str) -> bool:
        return self.rank > Severity(other).rank

    def __le__(self, other: str) -> bool:
        return self.rank <= Severity(other).rank

    def __lt__(self, other: str) -> bool:
        return self.rank < Severity(other).rank


class Confidence(StrEnum):
    """How a finding was established — never collapse this distinction into severity.

    CONFIRMED: read directly from structured input (e.g. "this action is delete").
    HEURISTIC: derived from a pattern or rule that could be wrong (e.g. resource category
        guessed from a type-name substring, or a dependency inferred from static references).
    UNKNOWN: InfraGuard could not determine enough to reach a conclusion; the finding exists
        to flag the gap, not to assert risk.
    """

    CONFIRMED = "confirmed"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    rule_id: str
    severity: Severity
    confidence: Confidence
    summary: str
    detail: str
    affected_resources: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    remediation: str | None = None


class PolicyDecision(BaseModel):
    decision: str  # "pass" | "warn" | "fail" | "error"
    exit_code: int
    reason: str
    triggered_finding_ids: list[str] = Field(default_factory=list)


class Report(BaseModel):
    schema_version: int = 1
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    module: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    inputs: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    policy_decision: PolicyDecision | None = None
    next_steps: list[str] = Field(default_factory=list)
