from pathlib import Path

import typer

from infraguard.cli.common import DB_PATH_OPTION
from infraguard.core.persistence import persist_report
from infraguard.core.reporting import render_json, render_markdown
from infraguard.errors import InfraGuardError
from infraguard.modules.change_analysis.analyzer import analyze_plan_file
from infraguard.modules.change_analysis.policy import load_policy_config

_VALID_FORMATS = ("json", "markdown", "both")


def register(app: typer.Typer) -> None:
    @app.command("analyze-change")
    def analyze_change(
        plan: Path = typer.Option(
            ..., "--plan", exists=True, readable=True, help="Path to a 'terraform show -json' plan file."
        ),
        policy: Path | None = typer.Option(
            None, "--policy", help="Path to a policy YAML file. Built-in defaults if omitted."
        ),
        report_format: str = typer.Option(
            "both", "--format", help="Report format to write: json | markdown | both."
        ),
        out: Path = typer.Option(
            Path("./infraguard-reports"), "--out", help="Directory to write report(s) into."
        ),
        db_path: Path = DB_PATH_OPTION,
    ) -> None:
        """Analyze a Terraform plan for change risk and apply CI policy."""
        if report_format not in _VALID_FORMATS:
            raise typer.BadParameter(f"--format must be one of {_VALID_FORMATS}")

        try:
            policy_config = load_policy_config(policy)
            report = analyze_plan_file(plan, policy_config)
        except InfraGuardError as exc:
            typer.echo(f"error: {exc.message}", err=True)
            raise typer.Exit(code=2) from exc

        persist_report(db_path, report)
        out.mkdir(parents=True, exist_ok=True)
        if report_format in ("json", "both"):
            json_path = out / f"{report.run_id}.json"
            json_path.write_text(render_json(report))
            typer.echo(f"wrote {json_path}")
        if report_format in ("markdown", "both"):
            md_path = out / f"{report.run_id}.md"
            md_path.write_text(render_markdown(report))
            typer.echo(f"wrote {md_path}")

        decision = report.policy_decision
        assert decision is not None
        typer.echo(
            f"{len(report.findings)} finding(s); policy decision: {decision.decision} — {decision.reason}"
        )
        raise typer.Exit(code=decision.exit_code)
