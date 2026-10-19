from unittest.mock import patch

from typer.testing import CliRunner

from infraguard.cli.app import app
from infraguard.modules.disaster_recovery.lab.availability import LabAvailability

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["recovery-lab", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "drill" in result.output


def _unavailable(*_args, **_kwargs) -> LabAvailability:
    return LabAvailability(False, "docker not installed (simulated for this test)")


def test_status_reports_unavailable_without_crashing() -> None:
    with patch(
        "infraguard.cli.commands.recovery_lab.check_lab_available", side_effect=_unavailable
    ):
        result = runner.invoke(app, ["recovery-lab", "status"])
    assert result.exit_code == 1
    assert "unavailable" in result.output


def test_start_fails_gracefully_when_lab_unavailable() -> None:
    with patch(
        "infraguard.cli.commands.recovery_lab.check_lab_available", side_effect=_unavailable
    ):
        result = runner.invoke(app, ["recovery-lab", "start"])
    assert result.exit_code == 2
    assert "unavailable" in result.output


def test_drill_fails_gracefully_when_lab_unavailable(tmp_path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        "policies:\n"
        "  - workload_id: wl\n"
        "    name: Test\n"
        "    rto_minutes: 60\n"
        "    rpo_minutes: 15\n"
        "    required_retention_days: 7\n"
        "    max_backup_age_hours: 24\n"
    )
    with patch(
        "infraguard.cli.commands.recovery_lab.check_lab_available", side_effect=_unavailable
    ):
        result = runner.invoke(
            app,
            [
                "recovery-lab",
                "drill",
                "--workload-id",
                "wl",
                "--policy",
                str(policy_file),
                "--evidence-out",
                str(tmp_path / "evidence.json"),
            ],
        )
    assert result.exit_code == 2
