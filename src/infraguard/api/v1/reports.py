from typing import Any

from fastapi import APIRouter, Request

from infraguard.core.reports_store import list_runs, load_report
from infraguard.errors import NotFoundError

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports_endpoint(
    request: Request, module: str | None = None, limit: int = 20
) -> dict[str, Any]:
    runs = list_runs(request.app.state.settings.db_path, module=module, limit=limit)
    return {"runs": runs}


@router.get("/{run_id}")
def get_report_endpoint(run_id: str, request: Request) -> dict[str, Any]:
    report = load_report(request.app.state.settings.db_path, run_id)
    if report is None:
        raise NotFoundError(f"No run found with run_id '{run_id}'", details={"run_id": run_id})
    return report.model_dump(mode="json")
