import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

from infraguard.core.persistence import persist_report
from infraguard.errors import InputValidationError
from infraguard.modules.failure_simulation.analyzer import (
    MAX_TOPOLOGY_SIZE_BYTES,
    simulate_failure,
    validate_topology,
)
from infraguard.modules.failure_simulation.models import FailureScenario

router = APIRouter(prefix="/failure-simulation", tags=["failure-simulation"])


class ValidateTopologyRequest(BaseModel):
    topology: dict[str, Any]


class SimulateFailureRequest(BaseModel):
    topology: dict[str, Any]
    scenario: FailureScenario


async def _read_json_body(request: Request) -> Any:
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TOPOLOGY_SIZE_BYTES:
        raise InputValidationError(
            f"Request body is {content_length} bytes, exceeding the "
            f"{MAX_TOPOLOGY_SIZE_BYTES}-byte limit.",
            details={"content_length": content_length, "max_bytes": MAX_TOPOLOGY_SIZE_BYTES},
        )
    raw_body = await request.body()
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Request body is not valid JSON: {exc}") from exc


@router.post("/validate-topology")
async def validate_topology_endpoint(request: Request) -> dict[str, Any]:
    body = await _read_json_body(request)
    try:
        parsed = ValidateTopologyRequest.model_validate(body)
    except ValidationError as exc:
        raise InputValidationError(f"Request body failed validation: {exc}") from exc
    report = validate_topology(parsed.topology, source="api")
    persist_report(request.app.state.settings.db_path, report)
    return report.model_dump(mode="json")


@router.post("/simulate-failure")
async def simulate_failure_endpoint(request: Request) -> dict[str, Any]:
    body = await _read_json_body(request)
    try:
        parsed = SimulateFailureRequest.model_validate(body)
    except ValidationError as exc:
        raise InputValidationError(f"Request body failed validation: {exc}") from exc
    report = simulate_failure(parsed.topology, parsed.scenario, source="api")
    persist_report(request.app.state.settings.db_path, report)
    return report.model_dump(mode="json")
