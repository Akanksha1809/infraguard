from pathlib import Path

import typer

from infraguard.core.reporting import render_json, render_markdown
from infraguard.errors import InfraGuardError
from infraguard.modules.failure_simulation.analyzer import (
    simulate_failure_file,
    validate_topology_file,
)
from infraguard.modules.failure_simulation.models import FailureScenario

_VALID_FORMATS = ("json", "markdown", "both")


def _write_reports(report, report_format: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if report_format in ("json", "both"):
        json_path = out / f"{report.run_id}.json"
        json_path.write_text(render_json(report))
        typer.echo(f"wrote {json_path}")
    if report_format in ("markdown", "both"):
        md_path = out / f"{report.run_id}.md"
        md_path.write_text(render_markdown(report))
        typer.echo(f"wrote {md_path}")


def register(app: typer.Typer) -> None:
    @app.command("validate-topology")
    def validate_topology(
        file: Path = typer.Option(
            ..., "--file", exists=True, readable=True, help="Path to a topology YAML/JSON file."
        ),
        report_format: str = typer.Option(
            "both", "--format", help="Report format to write: json | markdown | both."
        ),
        out: Path = typer.Option(
            Path("./infraguard-reports"), "--out", help="Directory to write report(s) into."
        ),
    ) -> None:
        """Validate a topology file and show its dependency graph."""
        if report_format not in _VALID_FORMATS:
            raise typer.BadParameter(f"--format must be one of {_VALID_FORMATS}")
        try:
            report = validate_topology_file(file)
        except InfraGuardError as exc:
            typer.echo(f"error: {exc.message}", err=True)
            raise typer.Exit(code=2) from exc

        _write_reports(report, report_format, out)
        typer.echo(f"{len(report.findings)} warning(s) found.")
        raise typer.Exit(code=0)

    @app.command("simulate-failure")
    def simulate_failure_cmd(
        topology: Path = typer.Option(
            ..., "--topology", exists=True, readable=True, help="Path to a topology YAML/JSON file."
        ),
        failure: list[str] = typer.Option(
            [], "--failure", help="Component id to fail. Repeatable for multiple failures."
        ),
        failure_domain: list[str] = typer.Option(
            [], "--failure-domain", help="Failure domain to fail entirely. Repeatable."
        ),
        report_format: str = typer.Option(
            "both", "--format", help="Report format to write: json | markdown | both."
        ),
        out: Path = typer.Option(
            Path("./infraguard-reports"), "--out", help="Directory to write report(s) into."
        ),
    ) -> None:
        """Simulate one or more component/failure-domain failures and report blast radius."""
        if report_format not in _VALID_FORMATS:
            raise typer.BadParameter(f"--format must be one of {_VALID_FORMATS}")
        if not failure and not failure_domain:
            raise typer.BadParameter("Provide at least one --failure or --failure-domain.")

        scenario = FailureScenario(
            name="cli-scenario", failed_component_ids=list(failure), failed_domains=list(failure_domain)
        )
        try:
            report = simulate_failure_file(topology, scenario)
        except InfraGuardError as exc:
            typer.echo(f"error: {exc.message}", err=True)
            raise typer.Exit(code=2) from exc

        _write_reports(report, report_format, out)
        cascaded = report.inputs.get("cascaded", [])
        typer.echo(
            f"{len(report.inputs.get('total_down', []))} component(s) down total "
            f"({len(cascaded)} cascaded); {len(report.findings)} finding(s)."
        )
        raise typer.Exit(code=0)
