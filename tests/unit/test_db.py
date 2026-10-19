from pathlib import Path

from infraguard.storage.db import SCHEMA_VERSION, get_connection, get_schema_version, init_db


def test_init_db_creates_schema(db_path: Path) -> None:
    assert get_schema_version(db_path) is None

    init_db(db_path)

    assert get_schema_version(db_path) == SCHEMA_VERSION


def test_init_db_is_idempotent(db_path: Path) -> None:
    init_db(db_path)
    init_db(db_path)  # must not raise, must not duplicate the schema_version row

    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()["n"]
    assert count == 1
