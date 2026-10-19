from pathlib import Path

from typer.testing import CliRunner

from infraguard.cli.app import app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "disaster_recovery"
runner = CliRunner()


def test_assess_recovery_cli_ready_exits_zero(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "assess-recovery",
            "--policy",
            str(FIXTURES_DIR / "policy_valid.yaml"),
            "--evidence",
            str(FIXTURES_DIR / "evidence_valid.json"),
            "--as-of",
            "2026-10-19T12:00:00Z",
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0
    assert len(list(out_dir.glob("*.json"))) == 1
    assert len(list(out_dir.glob("*.md"))) == 1


def test_assess_recovery_cli_errors_on_fatal_input(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "assess-recovery",
            "--policy",
            str(FIXTURES_DIR / "policy_duplicate.yaml"),
            "--evidence",
            str(FIXTURES_DIR / "evidence_valid.json"),
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 2


def test_assess_recovery_cli_rejects_bad_as_of(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "assess-recovery",
            "--policy",
            str(FIXTURES_DIR / "policy_valid.yaml"),
            "--evidence",
            str(FIXTURES_DIR / "evidence_valid.json"),
            "--as-of",
            "not-a-date",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0


def test_assess_recovery_cli_example_not_ready_exits_one(tmp_path: Path) -> None:
    examples_dir = Path(__file__).parent.parent.parent / "examples" / "recovery"
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "assess-recovery",
            "--policy",
            str(examples_dir / "policy.yaml"),
            "--evidence",
            str(examples_dir / "evidence.json"),
            "--as-of",
            "2026-10-19T12:00:00Z",
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 1
    assert "not_ready" in result.output or "insufficient_evidence" in result.output
