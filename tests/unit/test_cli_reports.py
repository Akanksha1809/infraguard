from pathlib import Path

from typer.testing import CliRunner

from infraguard.cli.app import app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "change_analysis"
runner = CliRunner()


def _run_analysis(tmp_path: Path) -> str:
    """Runs a real analyze-change and returns the run_id it persisted."""
    result = runner.invoke(
        app,
        [
            "analyze-change",
            "--plan",
            str(FIXTURES_DIR / "no_op_and_read.json"),
            "--out",
            str(tmp_path / "reports"),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0
    from infraguard.core.reports_store import list_runs

    runs = list_runs(tmp_path / "test.db")
    return runs[0]["run_id"]


def test_report_retrieves_a_persisted_run(tmp_path: Path) -> None:
    run_id = _run_analysis(tmp_path)

    result = runner.invoke(
        app, ["report", "--run-id", run_id, "--db-path", str(tmp_path / "test.db")]
    )

    assert result.exit_code == 0
    assert run_id in result.output
    assert "InfraGuard Report" in result.output


def test_report_json_format(tmp_path: Path) -> None:
    run_id = _run_analysis(tmp_path)

    result = runner.invoke(
        app,
        ["report", "--run-id", run_id, "--format", "json", "--db-path", str(tmp_path / "test.db")],
    )

    assert result.exit_code == 0
    assert '"run_id"' in result.output


def test_report_unknown_run_id_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["report", "--run-id", "nope", "--db-path", str(tmp_path / "test.db")]
    )
    assert result.exit_code == 2


def test_report_writes_to_out_dir_when_given(tmp_path: Path) -> None:
    run_id = _run_analysis(tmp_path)
    out_dir = tmp_path / "saved"

    result = runner.invoke(
        app,
        [
            "report",
            "--run-id",
            run_id,
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / f"{run_id}.md").exists()


def test_runs_lists_recent_runs(tmp_path: Path) -> None:
    _run_analysis(tmp_path)
    result = runner.invoke(app, ["runs", "--db-path", str(tmp_path / "test.db")])
    assert result.exit_code == 0
    assert "change_analysis" in result.output


def test_runs_empty_db_reports_none(tmp_path: Path) -> None:
    result = runner.invoke(app, ["runs", "--db-path", str(tmp_path / "empty.db")])
    assert result.exit_code == 0
    assert "No runs recorded" in result.output
