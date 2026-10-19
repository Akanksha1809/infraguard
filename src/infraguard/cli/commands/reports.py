"""`infraguard report` / `infraguard runs` — retrieve and list past runs from the shared
SQLite history every module writes to via `core.persistence.persist_report`.
"""

from pathlib import Path

import typer

from infraguard.cli.common import DB_PATH_OPTION
from infraguard.core.reporting import render_json, render_markdown
from infraguard.core.reports_store import list_runs, load_report
from infraguard.storage.db import init_db

_VALID_FORMATS = ("json", "markdown")


def register(app: typer.Typer) -> None:
    @app.command("report")
    def report_cmd(
        run_id: str = typer.Option(..., "--run-id", help="Run id to retrieve."),
        report_format: str = typer.Option("markdown", "--format", help="json | markdown."),
        out: Path | None = typer.Option(
            None, "--out", help="Optional directory to also save the report into."
        ),
        db_path: Path = DB_PATH_OPTION,
    ) -> None:
        """Retrieve a past run's report by run_id."""
        if report_format not in _VALID_FORMATS:
            raise typer.BadParameter(f"--format must be one of {_VALID_FORMATS}")

        init_db(db_path)
        report = load_report(db_path, run_id)
        if report is None:
            typer.echo(f"error: no run found with run_id '{run_id}'", err=True)
            raise typer.Exit(code=2)

        rendered = render_json(report) if report_format == "json" else render_markdown(report)
        typer.echo(rendered)

        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            ext = "json" if report_format == "json" else "md"
            path = out / f"{report.run_id}.{ext}"
            path.write_text(rendered)
            typer.echo(f"wrote {path}", err=True)

    @app.command("runs")
    def runs_cmd(
        module: str | None = typer.Option(
            None,
            "--module",
            help="Filter by module: change_analysis | failure_simulation | disaster_recovery",
        ),
        limit: int = typer.Option(20, "--limit", help="Maximum number of runs to show."),
        db_path: Path = DB_PATH_OPTION,
    ) -> None:
        """List recent runs (history) recorded across all modules."""
        init_db(db_path)
        runs = list_runs(db_path, module=module, limit=limit)
        if not runs:
            typer.echo("No runs recorded yet.")
            return
        for run in runs:
            typer.echo(f"{run['created_at']}  {run['module']:<20} {run['run_id']}")
