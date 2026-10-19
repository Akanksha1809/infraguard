from typer.testing import CliRunner

from infraguard.cli.app import app

runner = CliRunner()


def test_policy_show_default() -> None:
    result = runner.invoke(app, ["policy"])
    assert result.exit_code == 0
    assert "fail_on_severity_at_or_above: high" in result.output
    assert "destructive_delete" in result.output
    assert "single_point_of_failure" in result.output
    assert "no_restore_test" in result.output


def test_policy_show_filtered_by_module() -> None:
    result = runner.invoke(app, ["policy", "--module", "disaster_recovery"])
    assert result.exit_code == 0
    assert "no_restore_test" in result.output
    assert "destructive_delete" not in result.output
