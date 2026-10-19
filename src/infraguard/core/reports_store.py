"""Persist and retrieve `Report`s by run_id, shared by every module. This is what makes
"any past run can be retrieved later" (CLI `report --run-id`, API `GET /reports/{id}`) a
platform capability rather than something each module would otherwise reimplement.
"""

from pathlib import Path
from typing import Any

from infraguard.core.models import Report
from infraguard.storage.db import get_connection


def save_report(db_path: Path, report: Report) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, module, created_at, report_json) "
            "VALUES (?, ?, ?, ?)",
            (report.run_id, report.module, report.created_at.isoformat(), report.model_dump_json()),
        )
        conn.commit()


def load_report(db_path: Path, run_id: str) -> Report | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT report_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return Report.model_validate_json(row["report_json"])


def list_runs(
    db_path: Path, *, module: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        if module is not None:
            rows = conn.execute(
                "SELECT run_id, module, created_at FROM runs WHERE module = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (module, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT run_id, module, created_at FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [{"run_id": r["run_id"], "module": r["module"], "created_at": r["created_at"]} for r in rows]
