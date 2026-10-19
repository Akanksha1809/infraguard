from pathlib import Path

from typer.testing import CliRunner

from infraguard.cli.app import app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "failure_simulation"
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples" / "topologies"
runner = CliRunner()


def test_validate_topology_cli(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "validate-topology",
            "--file",
            str(FIXTURES_DIR / "simple_chain.yaml"),
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0
    assert len(list(out_dir.glob("*.json"))) == 1
    assert len(list(out_dir.glob("*.md"))) == 1


def test_validate_topology_cli_errors_on_fatal_input(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "validate-topology",
            "--file",
            str(FIXTURES_DIR / "duplicate_ids.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 2


def test_simulate_failure_cli_requires_a_failure_argument(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "simulate-failure",
            "--topology",
            str(FIXTURES_DIR / "simple_chain.yaml"),
            "--out",
            str(tmp_path / "out"),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code != 0


def test_simulate_failure_cli_component(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "simulate-failure",
            "--topology",
            str(FIXTURES_DIR / "simple_chain.yaml"),
            "--failure",
            "c",
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0
    assert "cascaded" in result.output or len(list(out_dir.glob("*.json"))) == 1


def test_simulate_failure_cli_domain_on_example(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    result = runner.invoke(
        app,
        [
            "simulate-failure",
            "--topology",
            str(EXAMPLES_DIR / "multi-zone-redundant.yaml"),
            "--failure-domain",
            "zone-a",
            "--out",
            str(out_dir),
            "--db-path",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code == 0
