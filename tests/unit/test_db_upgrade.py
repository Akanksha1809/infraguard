"""Confirms the additive schema-upgrade path: an existing v1 database (schema_version +
audit_events only, no 'runs' table) gets the 'runs' table added and its version bumped to
2 on the next init_db() call, with no data loss.
"""

import sqlite3
from pathlib import Path

from infraguard.storage.db import SCHEMA_VERSION, get_connection, init_db


def _create_v1_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            module TEXT,
            payload_json TEXT NOT NULL
        );
        INSERT INTO schema_version (version) VALUES (1);
        INSERT INTO audit_events (created_at, event_type, module, payload_json)
            VALUES ('2026-01-01T00:00:00Z', 'legacy.event', 'test', '{}');
        """
    )
    conn.commit()
    conn.close()


def test_upgrades_v1_database_in_place(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    _create_v1_database(db_path)

    init_db(db_path)

    with get_connection(db_path) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        preserved_event = conn.execute(
            "SELECT event_type FROM audit_events WHERE module = 'test'"
        ).fetchone()

    assert version == SCHEMA_VERSION
    assert "runs" in tables
    assert preserved_event["event_type"] == "legacy.event"
