"""Entry points tying policy/evidence parsing and the assessor together into a `Report` —
the only functions the CLI and API call.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from infraguard.core.models import Confidence, Finding, Report, Severity
from infraguard.errors import InputValidationError
from infraguard.modules.disaster_recovery.assessor import assess_workload
from infraguard.modules.disaster_recovery.models import BackupEvidence, RestoreDrillRecord
from infraguard.modules.disaster_recovery.validator import (
    parse_evidence_document,
    parse_policy_document,
)

MAX_DOCUMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB; a hand-authored policy/evidence file is never this large.

_ASSUMPTIONS = [
    "A backup's existence is never treated as evidence that it is recoverable — integrity "
    "verification and a successfully-verified restore test are tracked as separate facts.",
    "A dimension (integrity verified / restore tested / objectives demonstrated) is only "
    "ever TRUE or FALSE when there is direct evidence for it; otherwise it is UNKNOWN, "
    "never defaulted to either.",
    "'Most recent' backup/drill is determined by the latest 'taken_at'/'performed_at' "
    "timestamp in the supplied evidence, compared against the 'as_of' time (default: now).",
]
_LIMITATIONS = [
    "This assessment is only as complete as the supplied evidence document — it cannot "
    "detect a backup or drill that happened but was never recorded.",
    "Fixture-based drill evidence (source: 'fixture') is clearly labeled wherever it "
    "contributes to a 'ready' result, but is not itself a live-validated restore — see "
    "Milestone 5's local recovery lab for that.",
    "No overall numeric health score is produced; 'overall' is a three-way outcome shown "
    "alongside every individual finding, never a substitute for them.",
]


def _load_document(path: Path) -> Any:
    if not path.exists():
        raise InputValidationError(f"File not found: {path}")
    size = path.stat().st_size
    if size > MAX_DOCUMENT_SIZE_BYTES:
        raise InputValidationError(
            f"File '{path}' is {size} bytes, exceeding the {MAX_DOCUMENT_SIZE_BYTES}-byte limit.",
            details={"size_bytes": size, "max_bytes": MAX_DOCUMENT_SIZE_BYTES},
        )
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise InputValidationError(f"File '{path}' is not valid YAML/JSON: {exc}") from exc


def _group_by_workload(
    backups: list[BackupEvidence], drills: list[RestoreDrillRecord]
) -> tuple[dict[str, list[BackupEvidence]], dict[str, list[RestoreDrillRecord]]]:
    backups_by_workload: dict[str, list[BackupEvidence]] = {}
    for backup in backups:
        backups_by_workload.setdefault(backup.workload_id, []).append(backup)
    drills_by_workload: dict[str, list[RestoreDrillRecord]] = {}
    for drill in drills:
        drills_by_workload.setdefault(drill.workload_id, []).append(drill)
    return backups_by_workload, drills_by_workload


def assess_recovery(
    policy_raw: Any,
    evidence_raw: Any,
    *,
    as_of: datetime | None = None,
    source_policy: str | None = None,
    source_evidence: str | None = None,
) -> Report:
    as_of = as_of or datetime.now(UTC)
    policy_doc = parse_policy_document(policy_raw)
    evidence_doc = parse_evidence_document(evidence_raw)

    policy_by_workload = {p.workload_id: p for p in policy_doc.policies}
    known_ids = set(policy_by_workload)
    backups_by_workload, drills_by_workload = _group_by_workload(
        evidence_doc.backups, evidence_doc.drills
    )

    findings: list[Finding] = []
    evidence_workload_ids = set(backups_by_workload) | set(drills_by_workload)
    for workload_id in sorted(evidence_workload_ids - known_ids):
        findings.append(
            Finding(
                rule_id="evidence_for_unconfigured_workload",
                severity=Severity.MEDIUM,
                confidence=Confidence.CONFIRMED,
                summary=f"Evidence references '{workload_id}', which has no recovery policy",
                detail=(
                    f"Backup and/or drill evidence exists for '{workload_id}', but no "
                    "RecoveryPolicy defines its RTO/RPO/retention objectives, so it cannot "
                    "be assessed."
                ),
                affected_resources=[workload_id],
                remediation=f"Add a recovery policy for '{workload_id}', or remove the stray evidence.",
            )
        )

    readiness_list = []
    for workload_id, policy in policy_by_workload.items():
        readiness, workload_findings = assess_workload(
            policy,
            backups_by_workload.get(workload_id, []),
            drills_by_workload.get(workload_id, []),
            known_ids,
            as_of,
        )
        readiness_list.append(readiness)
        findings.extend(workload_findings)

    not_ready = [r for r in readiness_list if r.overall == "not_ready"]
    insufficient = [r for r in readiness_list if r.overall == "insufficient_evidence"]

    next_steps = []
    if not_ready:
        next_steps.append(
            f"{len(not_ready)} workload(s) are NOT READY: "
            f"{', '.join(r.workload_id for r in not_ready)}."
        )
    if insufficient:
        next_steps.append(
            f"{len(insufficient)} workload(s) have insufficient evidence to assess: "
            f"{', '.join(r.workload_id for r in insufficient)}."
        )
    if not next_steps:
        next_steps.append("All assessed workloads are ready, based on the evidence provided.")

    return Report(
        module="disaster_recovery",
        inputs={
            "source_policy": source_policy,
            "source_evidence": source_evidence,
            "as_of": as_of.isoformat(),
            "workload_count": len(policy_doc.policies),
            "readiness": [r.model_dump(mode="json") for r in readiness_list],
        },
        findings=findings,
        assumptions=_ASSUMPTIONS,
        limitations=_LIMITATIONS,
        next_steps=next_steps,
    )


def assess_recovery_files(
    policy_path: Path, evidence_path: Path, as_of: datetime | None = None
) -> Report:
    policy_raw = _load_document(policy_path)
    evidence_raw = _load_document(evidence_path)
    return assess_recovery(
        policy_raw,
        evidence_raw,
        as_of=as_of,
        source_policy=str(policy_path),
        source_evidence=str(evidence_path),
    )
