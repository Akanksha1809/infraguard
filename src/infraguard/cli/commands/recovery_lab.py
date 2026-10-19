"""`infraguard recovery-lab ...` — the optional local Docker/Postgres recovery lab.

Every command here first checks `check_lab_available()` and fails with a clear, specific
message (never a raw stack trace) when Docker isn't usable — the rest of InfraGuard (CLI,
API, the fixture-based `assess-recovery`) works with zero dependency on this being present.
"""

import json
from pathlib import Path

import typer
import yaml

from infraguard.modules.disaster_recovery.lab import workflow
from infraguard.modules.disaster_recovery.lab.availability import check_lab_available
from infraguard.modules.disaster_recovery.lab.compose import LabUnavailableError, is_running
from infraguard.modules.disaster_recovery.lab.workflow import DrillError
from infraguard.modules.disaster_recovery.models import BackupEvidence, RestoreDrillRecord
from infraguard.modules.disaster_recovery.validator import parse_evidence_document, parse_policy_document

lab_app = typer.Typer(
    name="recovery-lab",
    help="Optional local Docker/Postgres recovery drill lab (Milestone 5).",
    no_args_is_help=True,
)


def _require_lab(verbose: bool = True) -> None:
    availability = check_lab_available()
    if not availability.available:
        if verbose:
            typer.echo(f"error: recovery lab unavailable: {availability.reason}", err=True)
            typer.echo(
                "This is optional: 'assess-recovery' with fixture evidence still works "
                "without Docker.",
                err=True,
            )
        raise typer.Exit(code=2)


@lab_app.command("status")
def status() -> None:
    """Report whether the local recovery lab can run, and whether it's currently up."""
    availability = check_lab_available()
    if not availability.available:
        typer.echo(f"unavailable: {availability.reason}")
        raise typer.Exit(code=1)
    running = is_running()
    typer.echo(f"available: yes; running: {'yes' if running else 'no'}")


@lab_app.command("start")
def start() -> None:
    """Start the isolated lab Postgres container (step 1)."""
    _require_lab()
    try:
        workflow.start_lab()
    except LabUnavailableError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo("lab started.")


@lab_app.command("seed")
def seed() -> None:
    """Populate the deterministic sample dataset (step 2)."""
    _require_lab()
    try:
        checksum = workflow.seed_lab()
    except DrillError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"seeded {checksum['row_count']} row(s); digest={checksum['digest']}")


@lab_app.command("stop")
def stop() -> None:
    """Tear down the lab — only the resources this lab's own Compose project created."""
    _require_lab()
    try:
        workflow.stop_lab()
    except LabUnavailableError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo("lab stopped; its container and volume were removed.")


@lab_app.command("drill")
def drill(
    workload_id: str = typer.Option(..., "--workload-id", help="Workload id to record evidence under."),
    policy: Path = typer.Option(
        ..., "--policy", exists=True, readable=True, help="Recovery policy file (for RTO/RPO/retention)."
    ),
    evidence_out: Path = typer.Option(
        ...,
        "--evidence-out",
        help="Evidence JSON/YAML file to append this drill's results into (created if absent).",
    ),
    backups_dir: Path = typer.Option(
        Path("./infraguard-lab-backups"), "--backups-dir", help="Where to write the pg_dump file."
    ),
) -> None:
    """Run the full drill: start -> seed -> backup -> induce data loss -> restore -> verify
    -> record (steps 2-9 of the brief's workflow; run 'start' separately first if you want
    to inspect the lab before seeding, otherwise this starts it for you).
    """
    _require_lab()

    policy_doc = parse_policy_document(yaml.safe_load(policy.read_text()))
    matching = [p for p in policy_doc.policies if p.workload_id == workload_id]
    if not matching:
        typer.echo(f"error: no policy found for workload_id '{workload_id}' in {policy}", err=True)
        raise typer.Exit(code=2)
    workload_policy = matching[0]

    try:
        workflow.start_lab()
        backup_evidence, drill_record = workflow.run_full_drill(
            workload_id, backups_dir, retention_days=workload_policy.required_retention_days
        )
    except (LabUnavailableError, DrillError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _append_evidence(evidence_out, backup_evidence, drill_record)

    typer.echo(f"backup: {backup_evidence.backup_id} ({backup_evidence.size_bytes} bytes)")
    typer.echo(
        f"restore verification: {'PASSED' if drill_record.verification_passed else 'FAILED'} "
        f"in {drill_record.restore_duration_minutes} min "
        f"(RTO {workload_policy.rto_minutes} min); "
        f"data_loss={drill_record.data_loss_minutes} min (RPO {workload_policy.rpo_minutes} min)"
    )
    typer.echo(f"appended evidence to {evidence_out}")
    typer.echo("Run 'infraguard recovery-lab stop' when done, and 'infraguard assess-recovery' to evaluate.")


def _append_evidence(path: Path, backup: BackupEvidence, drill_record: RestoreDrillRecord) -> None:
    if path.exists():
        existing = parse_evidence_document(yaml.safe_load(path.read_text()) or {})
    else:
        existing = parse_evidence_document({})

    existing.backups.append(backup)
    existing.drills.append(drill_record)
    path.write_text(
        json.dumps(
            {
                "backups": [b.model_dump(mode="json") for b in existing.backups],
                "drills": [d.model_dump(mode="json") for d in existing.drills],
            },
            indent=2,
        )
    )


def register(app: typer.Typer) -> None:
    app.add_typer(lab_app)
