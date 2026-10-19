import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

from infraguard.core.persistence import persist_report
from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.analyzer import MAX_PLAN_SIZE_BYTES, analyze_plan
from infraguard.modules.change_analysis.policy import PolicyConfig

router = APIRouter(prefix="/change-analysis", tags=["change-analysis"])


class AnalyzeChangeRequest(BaseModel):
    plan: dict[str, Any]
    policy: PolicyConfig | None = None


@router.post("/analyze")
async def analyze_change(request: Request) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_PLAN_SIZE_BYTES:
        raise InputValidationError(
            f"Request body is {content_length} bytes, exceeding the "
            f"{MAX_PLAN_SIZE_BYTES}-byte limit.",
            details={"content_length": content_length, "max_bytes": MAX_PLAN_SIZE_BYTES},
        )

    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Request body is not valid JSON: {exc}") from exc

    try:
        parsed_request = AnalyzeChangeRequest.model_validate(body)
    except ValidationError as exc:
        raise InputValidationError(f"Request body failed validation: {exc}") from exc

    report = analyze_plan(parsed_request.plan, parsed_request.policy, source="api")
    persist_report(request.app.state.settings.db_path, report)
    return report.model_dump(mode="json")
