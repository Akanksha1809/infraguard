"""Parse and structurally validate a recovery policy document or an evidence document.

Fatal problems (not an object, schema validation failure, duplicate workload_id across
policies) raise `InputValidationError`. Cross-referencing policies against evidence (e.g.
"this backup references a workload with no policy") is the assessor's job, not the
validator's — a document can be structurally valid on its own and still need that check.
"""

from typing import Any

from pydantic import ValidationError

from infraguard.errors import InputValidationError
from infraguard.modules.disaster_recovery.models import EvidenceDocument, PolicyDocument


def parse_policy_document(raw: Any) -> PolicyDocument:
    if not isinstance(raw, dict):
        raise InputValidationError("Recovery policy document root must be an object.")
    try:
        document = PolicyDocument.model_validate(raw)
    except ValidationError as exc:
        raise InputValidationError(f"Recovery policy document failed validation: {exc}") from exc

    seen: set[str] = set()
    duplicates: set[str] = set()
    for policy in document.policies:
        if policy.workload_id in seen:
            duplicates.add(policy.workload_id)
        seen.add(policy.workload_id)
    if duplicates:
        raise InputValidationError(
            f"Duplicate workload_id(s) in policy document: {sorted(duplicates)}.",
            details={"duplicate_workload_ids": sorted(duplicates)},
        )

    return document


def parse_evidence_document(raw: Any) -> EvidenceDocument:
    if not isinstance(raw, dict):
        raise InputValidationError("Recovery evidence document root must be an object.")
    try:
        return EvidenceDocument.model_validate(raw)
    except ValidationError as exc:
        raise InputValidationError(f"Recovery evidence document failed validation: {exc}") from exc
