"""The one function every module's CLI command and API endpoint calls after producing a
`Report`: save it for later retrieval and record an audit event. Centralizing this means
all three modules get the same history/audit behavior automatically, with nothing
module-specific to remember.
"""

from pathlib import Path
from typing import Any

from infraguard.core.audit import record_event
from infraguard.core.models import Report
from infraguard.core.reports_store import save_report
from infraguard.storage.db import init_db


def persist_report(db_path: Path, report: Report) -> None:
    init_db(db_path)  # CLI commands have no other startup hook that creates the schema.
    save_report(db_path, report)
    summary: dict[str, Any] = {"run_id": report.run_id, "finding_count": len(report.findings)}
    if report.policy_decision is not None:
        summary["decision"] = report.policy_decision.decision
    record_event(db_path, f"{report.module}.run_completed", summary, module=report.module)
