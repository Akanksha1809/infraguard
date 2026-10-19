from datetime import UTC, datetime
from pathlib import Path

import pytest

from infraguard.modules.disaster_recovery.models import (
    BackupEvidence,
    RecoveryPolicy,
    RestoreDrillRecord,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "disaster_recovery"

AS_OF = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def as_of() -> datetime:
    return AS_OF


@pytest.fixture
def fixture_path():
    def _path(name: str) -> Path:
        return FIXTURES_DIR / name

    return _path


def make_policy(**overrides) -> RecoveryPolicy:
    defaults = dict(
        workload_id="wl",
        name="Workload",
        rto_minutes=60,
        rpo_minutes=15,
        required_retention_days=30,
        max_backup_age_hours=24,
        required_integrity_check=True,
    )
    defaults.update(overrides)
    return RecoveryPolicy(**defaults)


def make_backup(**overrides) -> BackupEvidence:
    defaults = dict(
        workload_id="wl",
        backup_id="b1",
        taken_at=AS_OF,
        retention_days=30,
        integrity_check_passed=True,
    )
    defaults.update(overrides)
    return BackupEvidence(**defaults)


def make_drill(**overrides) -> RestoreDrillRecord:
    defaults = dict(
        workload_id="wl",
        drill_id="d1",
        source="fixture",
        performed_at=AS_OF,
        verification_passed=True,
        restore_duration_minutes=10,
        data_loss_minutes=5,
    )
    defaults.update(overrides)
    return RestoreDrillRecord(**defaults)


@pytest.fixture
def policy_factory():
    return make_policy


@pytest.fixture
def backup_factory():
    return make_backup


@pytest.fixture
def drill_factory():
    return make_drill
