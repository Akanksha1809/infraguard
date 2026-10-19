from infraguard.modules.disaster_recovery.lab import dataset
from infraguard.modules.disaster_recovery.lab.constants import SEED_ROW_COUNT, TABLE_NAME


def test_seed_rows_is_deterministic() -> None:
    assert dataset.seed_rows() == dataset.seed_rows()


def test_seed_rows_count_matches_constant() -> None:
    assert len(dataset.seed_rows()) == SEED_ROW_COUNT


def test_seed_rows_have_unique_sequential_ids() -> None:
    ids = [r["id"] for r in dataset.seed_rows()]
    assert ids == list(range(1, SEED_ROW_COUNT + 1))


def test_create_table_sql_mentions_table_name() -> None:
    assert TABLE_NAME in dataset.create_table_sql()


def test_insert_rows_sql_contains_every_row() -> None:
    rows = dataset.seed_rows()[:3]
    sql = dataset.insert_rows_sql(rows)
    for row in rows:
        assert row["customer"] in sql


def test_parse_checksum_row_round_trip() -> None:
    raw = "50|12737.25|abcdef1234567890"
    parsed = dataset.parse_checksum_row(raw)
    assert parsed == {"row_count": 50, "total_amount": 12737.25, "digest": "abcdef1234567890"}


def test_parse_checksum_row_handles_trailing_newline() -> None:
    raw = "0|0|\n"
    parsed = dataset.parse_checksum_row(raw)
    assert parsed["row_count"] == 0
    assert parsed["digest"] == ""
