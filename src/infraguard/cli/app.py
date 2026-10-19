"""CLI skeleton. Module commands (analyze-change, validate-topology, simulate-failure,
assess-recovery, report) are added as each module lands; this skeleton only wires up the
app, version, and serve commands so the tool installs and runs end-to-end from Milestone 1.
"""

import typer
import uvicorn

from infraguard import __version__
from infraguard.cli.commands import (
    change_analysis,
    disaster_recovery,
    failure_simulation,
    policy,
    recovery_lab,
    reports,
)
from infraguard.config import get_settings

app = typer.Typer(
    name="infraguard",
    help="Infrastructure reliability and resilience engineering platform.",
    no_args_is_help=True,
)

change_analysis.register(app)
failure_simulation.register(app)
disaster_recovery.register(app)
recovery_lab.register(app)
reports.register(app)
policy.register(app)


@app.command()
def version() -> None:
    """Print the InfraGuard version."""
    typer.echo(__version__)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development only)."),
) -> None:
    """Run the FastAPI server."""
    get_settings()  # fail fast on invalid configuration before starting the server
    uvicorn.run(
        "infraguard.api.app:create_app", factory=True, host=host, port=port, reload=reload
    )
