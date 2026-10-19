import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

from infraguard.errors import InputValidationError
from infraguard.modules.disaster_recovery.analyzer import (
    MAX_DOCUMENT_SIZE_BYTES,
    assess_recovery,
)

router = APIRouter(prefix="/disaster-recovery", tags=["disaster-recovery"])


class AssessRecoveryRequest(BaseModel):
    policy: dict[str, Any]
    evidence: dict[str, Any]
    as_of: datetime | None = None


@router.post("/assess-recovery")
async def assess_recovery_endpoint(request: Request) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_DOCUMENT_SIZE_BYTES:
        raise InputValidationError(
            f"Request body is {content_length} bytes, exceeding the "
            f"{MAX_DOCUMENT_SIZE_BYTES}-byte limit.",
            details={"content_length": content_length, "max_bytes": MAX_DOCUMENT_SIZE_BYTES},
        )

    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Request body is not valid JSON: {exc}") from exc

    try:
        parsed = AssessRecoveryRequest.model_validate(body)
    except ValidationError as exc:
        raise InputValidationError(f"Request body failed validation: {exc}") from exc

    report = assess_recovery(
        parsed.policy,
        parsed.evidence,
        as_of=parsed.as_of,
        source_policy="api",
        source_evidence="api",
    )
    return report.model_dump(mode="json")
