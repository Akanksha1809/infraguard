"""Orchestrates the controlled local recovery drill: start the lab, seed deterministic
data, back it up, induce a *scoped* data-loss scenario (truncate the lab's own one table),
restore, and verify — producing real `BackupEvidence`/`RestoreDrillRecord` (source:
"live_lab") that feed straight into the same assessor Milestone 4 built for fixture
evidence.

Safety: `induce_data_loss` only ever truncates the lab's own table in its own database,
never anything else. Teardown (`stop_lab`) is a separate, explicit step — a drill never
tears the lab down on its own, so its state can be inspected afterward if useful.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from infraguard.modules.disaster_recovery.lab import dataset
from infraguard.modules.disaster_recovery.lab.compose import down, exec_in_container, up
from infraguard.modules.disaster_recovery.lab.constants import DB_NAME, DB_USER, TABLE_NAME
from infraguard.modules.disaster_recovery.models import BackupEvidence, RestoreDrillRecord


class DrillError(RuntimeError):
    """A step of the drill failed in a way that is not itself the point being measured
    (e.g. the database never came up) — distinct from a failed *verification*, which is a
    normal, reportable outcome, not an exception.
    """


def _psql(sql: str, timeout: int = 30) -> str:
    result = exec_in_container(
        ["psql", "-U", DB_USER, "-d", DB_NAME, "-v", "ON_ERROR_STOP=1", "-t", "-A", "-F", "|"],
        stdin_bytes=sql.encode(),
        timeout=timeout,
    )
    if result.returncode != 0:
        raise DrillError(f"psql command failed: {result.stderr.decode(errors='replace')}")
    return result.stdout.decode()


def start_lab() -> None:
    up()


def stop_lab() -> None:
    down(remove_volumes=True)


def seed_lab() -> dict:
    """Populate the deterministic dataset and return its checksum fingerprint."""
    rows = dataset.seed_rows()
    _psql(dataset.create_table_sql())
    _psql(dataset.insert_rows_sql(rows))
    return dataset.parse_checksum_row(_psql(dataset.CHECKSUM_SQL))


def create_backup(backups_dir: Path) -> tuple[str, Path, bool]:
    """pg_dump the lab database to a local file. Returns (backup_id, path, dump_succeeded).

    `dump_succeeded` is this milestone's integrity check: pg_dump exited cleanly and
    produced a non-empty file. This is a structural check (the dump process completed),
    not a full archive-validity scan — see docs/DISASTER_RECOVERY.md's stated limitations.
    """
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"lab-backup-{timestamp}-{uuid4().hex[:6]}"
    backup_path = backups_dir / f"{backup_id}.dump"

    result = exec_in_container(["pg_dump", "-U", DB_USER, "-F", "custom", DB_NAME], timeout=60)
    dump_succeeded = result.returncode == 0 and bool(result.stdout)
    if dump_succeeded:
        backup_path.write_bytes(result.stdout)
    return backup_id, backup_path, dump_succeeded


def induce_data_loss() -> None:
    """The controlled, scoped data-loss scenario: truncate exactly one table in the lab's
    own database. Nothing else — not another table, not another database, not a volume —
    is ever touched by this function.
    """
    _psql(f"TRUNCATE TABLE {TABLE_NAME};")


def restore_backup(backup_path: Path) -> str:
    """Restore the dump back into the lab database. pg_restore commonly exits non-zero on
    harmless warnings even on a successful restore (e.g. 'role does not exist' against a
    fresh target), so its exit code is not treated as the pass/fail signal here — the
    checksum comparison after this call is. stderr is returned for the record.
    """
    data = backup_path.read_bytes()
    result = exec_in_container(
        ["pg_restore", "-U", DB_USER, "-d", DB_NAME, "--clean", "--if-exists"],
        stdin_bytes=data,
        timeout=60,
    )
    return result.stderr.decode(errors="replace")


def run_full_drill(
    workload_id: str, backups_dir: Path, *, retention_days: int
) -> tuple[BackupEvidence, RestoreDrillRecord]:
    """Runs steps 2-9 of the brief's local-lab workflow in sequence. Assumes `start_lab()`
    has already been called (step 1) — see the `recovery-lab` CLI command group.
    """
    expected = seed_lab()

    backup_id, backup_path, dump_succeeded = create_backup(backups_dir)
    backup_taken_at = datetime.now(UTC)

    restore_started_at = datetime.now(UTC)
    induce_data_loss()
    restore_stderr = restore_backup(backup_path)
    restore_completed_at = datetime.now(UTC)

    actual = dataset.parse_checksum_row(_psql(dataset.CHECKSUM_SQL))
    verification_passed = actual == expected

    restore_duration_minutes = (restore_completed_at - restore_started_at).total_seconds() / 60
    data_loss_minutes = (restore_started_at - backup_taken_at).total_seconds() / 60

    backup_evidence = BackupEvidence(
        workload_id=workload_id,
        backup_id=backup_id,
        taken_at=backup_taken_at,
        retention_days=retention_days,
        integrity_check_passed=dump_succeeded,
        integrity_checked_at=backup_taken_at,
        size_bytes=backup_path.stat().st_size if backup_path.exists() else None,
        location=str(backup_path),
    )

    notes = f"expected={expected}, actual={actual}"
    if restore_stderr.strip():
        notes += f"\npg_restore stderr: {restore_stderr.strip()}"

    drill_record = RestoreDrillRecord(
        workload_id=workload_id,
        drill_id=f"lab-drill-{restore_completed_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:6]}",
        source="live_lab",
        performed_at=restore_completed_at,
        backup_id=backup_id,
        restore_duration_minutes=round(restore_duration_minutes, 4),
        verification_passed=verification_passed,
        verification_method=(
            "SQL-side row count + sum(amount) + order-sensitive md5 digest, compared "
            "before data loss vs. after restore"
        ),
        data_loss_minutes=round(max(data_loss_minutes, 0.0), 4),
        notes=notes,
    )

    return backup_evidence, drill_record
