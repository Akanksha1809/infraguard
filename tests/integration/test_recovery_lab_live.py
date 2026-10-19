"""Real, live tests against an actual Docker Postgres container — not mocks. These are the
tests the project brief calls out as "optional tests that cannot run due to missing local
tools": they SKIP (visibly, with a reason) when Docker isn't available, rather than failing
or silently passing. On a machine with Docker, they really do start a container, truncate a
real table, restore a real pg_dump, and tear everything down again.
"""

from pathlib import Path

import pytest

from infraguard.modules.disaster_recovery.lab import workflow
from infraguard.modules.disaster_recovery.lab.availability import check_lab_available
from infraguard.modules.disaster_recovery.lab.compose import exec_in_container, is_running
from infraguard.modules.disaster_recovery.lab.constants import DB_NAME, DB_USER, TABLE_NAME

_availability = check_lab_available()
pytestmark = pytest.mark.skipif(
    not _availability.available,
    reason=f"Docker recovery lab unavailable: {_availability.reason}",
)


@pytest.fixture
def running_lab():
    workflow.start_lab()
    try:
        yield
    finally:
        workflow.stop_lab()


def _row_count() -> str:
    result = exec_in_container(
        ["psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-c", f"SELECT COUNT(*) FROM {TABLE_NAME};"]
    )
    return result.stdout.decode().strip()


def test_lab_starts_and_is_reported_running(running_lab) -> None:
    assert is_running()


def test_seeding_is_deterministic_across_reseeds(running_lab) -> None:
    first = workflow.seed_lab()
    second = workflow.seed_lab()  # DROP + CREATE + INSERT again
    assert first == second


def test_induce_data_loss_actually_empties_the_table(running_lab) -> None:
    workflow.seed_lab()
    assert _row_count() != "0"
    workflow.induce_data_loss()
    assert _row_count() == "0"


def test_full_drill_backs_up_wipes_restores_and_verifies(running_lab, tmp_path: Path) -> None:
    backup_evidence, drill = workflow.run_full_drill(
        "live-test-workload", tmp_path, retention_days=7
    )

    assert backup_evidence.workload_id == "live-test-workload"
    assert backup_evidence.integrity_check_passed is True
    assert backup_evidence.size_bytes and backup_evidence.size_bytes > 0
    assert Path(backup_evidence.location).exists()

    assert drill.source == "live_lab"
    assert drill.verification_passed is True
    assert drill.restore_duration_minutes is not None
    assert drill.restore_duration_minutes >= 0
    assert drill.data_loss_minutes is not None

    # The table is non-empty again after the drill's restore step.
    assert _row_count() != "0"


def test_stop_lab_removes_the_container() -> None:
    workflow.start_lab()
    assert is_running()
    workflow.stop_lab()
    assert not is_running()
