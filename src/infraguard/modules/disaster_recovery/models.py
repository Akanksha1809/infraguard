"""Recovery policy, evidence, and readiness models.

The central rule this module exists to enforce, stated once here rather than scattered:
**a backup's existence is never evidence that it is recoverable.** Five distinct questions
are tracked separately and never collapsed into one another: is a policy configured, does
backup evidence exist, was its integrity verified, was a restore actually tested, and were
the RTO/RPO objectives demonstrated by a *measured* result.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class RecoveryPolicy(BaseModel):
    workload_id: str
    name: str
    rto_minutes: float
    """Recovery Time Objective: maximum acceptable time to restore service."""
    rpo_minutes: float
    """Recovery Point Objective: maximum acceptable data-loss window."""
    required_retention_days: int
    max_backup_age_hours: float
    """How old the most recent backup may be before it is considered stale."""
    required_integrity_check: bool = True
    required_restore_test_interval_days: int | None = None
    """How often a successfully-verified restore test must have occurred for the restore
    test to count as current rather than stale. None = never considered stale by age."""
    depends_on: list[str] = Field(default_factory=list)
    """Other workload_ids this workload's recovery depends on (e.g. a shared secrets
    store). Each must itself have a configured policy and backup evidence, or a
    'missing_recovery_dependency' finding is raised."""


class BackupEvidence(BaseModel):
    workload_id: str
    backup_id: str
    taken_at: datetime
    retention_days: int
    integrity_check_passed: bool | None = None
    """None means not checked — never treated as passing."""
    integrity_checked_at: datetime | None = None
    size_bytes: int | None = None
    location: str | None = None


class RestoreDrillRecord(BaseModel):
    workload_id: str
    drill_id: str
    source: Literal["fixture", "live_lab"] = "fixture"
    """'fixture' means this evidence was supplied as a file, not produced by an actual
    restore. Every report says so explicitly wherever this record is used — see
    docs/DISASTER_RECOVERY.md. 'live_lab' is produced by the Milestone 5 Docker/Postgres lab."""
    performed_at: datetime
    backup_id: str | None = None
    restore_duration_minutes: float | None = None
    """Measured wall-clock time for the restore. None means not recorded — never assumed
    to meet RTO."""
    verification_passed: bool | None = None
    verification_method: str | None = None
    data_loss_minutes: float | None = None
    """Measured gap between the backup's data cutoff and the point being recovered to —
    the actual RPO achieved by this drill. None means not recorded."""
    notes: str | None = None


class ReadinessDimension(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    """Not enough evidence exists to say true or false — never defaulted to either."""


class WorkloadReadiness(BaseModel):
    workload_id: str
    policy_configured: bool
    backup_evidence_present: bool
    backup_integrity_verified: ReadinessDimension
    restore_successfully_tested: ReadinessDimension
    recovery_objectives_demonstrated: ReadinessDimension
    overall: Literal["ready", "not_ready", "insufficient_evidence"]
    uses_fixture_evidence: bool
    """True if any drill backing this assessment has source == 'fixture' rather than
    'live_lab'. Always surfaced so a fixture-based 'ready' is never mistaken for a
    live-validated one."""


class PolicyDocument(BaseModel):
    policies: list[RecoveryPolicy] = Field(default_factory=list)


class EvidenceDocument(BaseModel):
    backups: list[BackupEvidence] = Field(default_factory=list)
    drills: list[RestoreDrillRecord] = Field(default_factory=list)


class DocumentWarning(BaseModel):
    code: str
    message: str
