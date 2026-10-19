"""Shared CLI option definitions, so every report-producing command takes `--db-path` the
same way instead of four slightly different copies.
"""

from pathlib import Path

import typer

DB_PATH_OPTION = typer.Option(
    Path("./infraguard.db"),
    "--db-path",
    envvar="INFRAGUARD_DB_PATH",
    help="SQLite database for run history/audit (matches the server's default; override "
    "for test isolation or a separate history file).",
)
