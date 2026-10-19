from pathlib import Path

from typer.testing import CliRunner

from infraguard.cli.app import app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "change_analysis"
runner = CliRunner()


def test_analyze_change_writes_reports_and_exits_nonzero_on_fail(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "analyze-change",
            "--plan",
            str(FIXTURES_DIR / "delete_database.json"),
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )

    assert result.exit_code == 1  # CRITICAL finding trips the default fail threshold
    json_reports = list(out_dir.glob("*.json"))
    md_reports = list(out_dir.glob("*.md"))
    assert len(json_reports) == 1
    assert len(md_reports) == 1


def test_analyze_change_passes_on_clean_plan(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "analyze-change",
            "--plan",
            str(FIXTURES_DIR / "no_op_and_read.json"),
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0


def test_analyze_change_errors_on_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "analyze-change",
            "--plan",
            str(tmp_path / "missing.json"),
            "--out",
            str(tmp_path / "out"),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code != 0


def test_analyze_change_rejects_invalid_format(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "analyze-change",
            "--plan",
            str(FIXTURES_DIR / "no_op_and_read.json"),
            "--format",
            "yaml",
            "--out",
            str(tmp_path / "out"),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code != 0
