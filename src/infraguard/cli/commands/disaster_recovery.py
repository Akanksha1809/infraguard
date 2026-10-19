from datetime import datetime
from pathlib import Path

import typer

from infraguard.core.reporting import render_json, render_markdown
from infraguard.errors import InfraGuardError
from infraguard.modules.disaster_recovery.analyzer import assess_recovery_files

_VALID_FORMATS = ("json", "markdown", "both")


def register(app: typer.Typer) -> None:
    @app.command("assess-recovery")
    def assess_recovery_cmd(
        policy: Path = typer.Option(
            ..., "--policy", exists=True, readable=True, help="Path to a recovery policy YAML/JSON file."
        ),
        evidence: Path = typer.Option(
            ...,
            "--evidence",
            exists=True,
            readable=True,
            help="Path to a recovery evidence (backups/drills) YAML/JSON file.",
        ),
        as_of: str | None = typer.Option(
            None,
            "--as-of",
            help="ISO8601 timestamp to evaluate staleness against (default: now); for reproducible runs.",
        ),
        report_format: str = typer.Option(
            "both", "--format", help="Report format to write: json | markdown | both."
        ),
        out: Path = typer.Option(
            Path("./infraguard-reports"), "--out", help="Directory to write report(s) into."
        ),
    ) -> None:
        """Assess disaster-recovery readiness from a policy file and an evidence file."""
        if report_format not in _VALID_FORMATS:
            raise typer.BadParameter(f"--format must be one of {_VALID_FORMATS}")

        as_of_dt = None
        if as_of is not None:
            try:
                as_of_dt = datetime.fromisoformat(as_of)
            except ValueError as exc:
                raise typer.BadParameter(f"--as-of must be ISO8601: {exc}") from exc

        try:
            report = assess_recovery_files(policy, evidence, as_of=as_of_dt)
        except InfraGuardError as exc:
            typer.echo(f"error: {exc.message}", err=True)
            raise typer.Exit(code=2) from exc

        out.mkdir(parents=True, exist_ok=True)
        if report_format in ("json", "both"):
            json_path = out / f"{report.run_id}.json"
            json_path.write_text(render_json(report))
            typer.echo(f"wrote {json_path}")
        if report_format in ("markdown", "both"):
            md_path = out / f"{report.run_id}.md"
            md_path.write_text(render_markdown(report))
            typer.echo(f"wrote {md_path}")

        readiness = report.inputs.get("readiness", [])
        not_ready = [r for r in readiness if r["overall"] != "ready"]
        for r in readiness:
            typer.echo(f"  {r['workload_id']}: {r['overall']}")
        typer.echo(
            f"{len(report.findings)} finding(s); {len(not_ready)}/{len(readiness)} workload(s) not ready."
        )
        raise typer.Exit(code=1 if not_ready else 0)
