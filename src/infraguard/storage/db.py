"""SQLite connection and schema management.

No migration framework: the schema is created idempotently (`CREATE TABLE IF NOT EXISTS`)
and every change is additive, tracked by a single row in `schema_version`. This is
deliberately simple per the project's "avoid a migration framework unless complexity
justifies it" constraint — revisit only if additive changes stop being sufficient.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    module TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events (created_at);

-- Added in schema v2: one row per module run (change analysis / failure simulation /
-- disaster recovery), the full Report as JSON, so any past run can be retrieved later.
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_module ON runs (module);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at);
"""


@contextmanager
def get_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Create the schema if absent, and upgrade in place if an older version exists.

    Upgrades are purely additive (new tables only, via `CREATE TABLE IF NOT EXISTS`), so
    "upgrading" is just: run the current full schema script (safe against an existing v1
    database — it only adds what's missing), then bump the recorded version number. No
    data transformation is ever needed as long as this stays additive-only; a column
    change or removal would be the signal to introduce a real migration tool.
    """
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] < SCHEMA_VERSION:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        conn.commit()


def get_schema_version(db_path: Path) -> int | None:
    """Return the current schema version, or None if `init_db` has never run."""
    with get_connection(db_path) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if table is None:
            return None
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row["version"] if row else None
