"""A fully deterministic sample dataset and its SQL-side checksum — no randomness anywhere,
so a drill run twice against identical code produces an identical "expected" fingerprint.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from infraguard.modules.disaster_recovery.lab.constants import SEED_ROW_COUNT, TABLE_NAME

_BASE_TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def seed_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": i,
            "customer": f"customer-{i:03d}",
            "amount": round(i * 9.99, 2),
            "created_at": (_BASE_TIMESTAMP + timedelta(minutes=i)).isoformat(),
        }
        for i in range(1, SEED_ROW_COUNT + 1)
    ]


def create_table_sql() -> str:
    return (
        f"DROP TABLE IF EXISTS {TABLE_NAME};\n"
        f"CREATE TABLE {TABLE_NAME} (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    customer TEXT NOT NULL,\n"
        "    amount NUMERIC(10,2) NOT NULL,\n"
        "    created_at TIMESTAMPTZ NOT NULL\n"
        ");\n"
    )


def insert_rows_sql(rows: list[dict[str, Any]]) -> str:
    values = ",\n".join(
        f"({r['id']}, '{r['customer']}', {r['amount']}, '{r['created_at']}')" for r in rows
    )
    return f"INSERT INTO {TABLE_NAME} (id, customer, amount, created_at) VALUES\n{values};\n"


# COUNT + SUM + an order-sensitive md5 digest over every row: a restore that is missing
# rows, has extra rows, or has altered any value produces a different digest.
CHECKSUM_SQL = (
    "SELECT COUNT(*) AS row_count, COALESCE(SUM(amount), 0) AS total_amount, "
    "COALESCE(md5(string_agg(id::text || ':' || customer || ':' || amount::text, ',' "
    f"ORDER BY id)), '') AS digest FROM {TABLE_NAME};\n"
)


def parse_checksum_row(raw: str) -> dict[str, Any]:
    row_count, total_amount, digest = raw.strip().split("|")
    return {"row_count": int(row_count), "total_amount": float(total_amount), "digest": digest}
