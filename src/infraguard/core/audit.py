"""Append-only audit trail, shared by every module and interface.

Modules call `record_event` instead of writing to SQLite directly, so the audit log has one
consistent shape (`event_type`, optional `module`, a JSON payload, a timestamp) regardless of
which module or interface produced the event.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infraguard.storage.db import get_connection


def record_event(
    db_path: Path, event_type: str, payload: dict[str, Any], *, module: str | None = None
) -> int:
    created_at = datetime.now(UTC).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO audit_events (created_at, event_type, module, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (created_at, event_type, module, json.dumps(payload, default=str)),
        )
        conn.commit()
        assert cursor.lastrowid is not None  # always set after an INSERT into a rowid table
        return cursor.lastrowid


def list_events(db_path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, event_type, module, payload_json "
            "FROM audit_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "event_type": row["event_type"],
                "module": row["module"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]
