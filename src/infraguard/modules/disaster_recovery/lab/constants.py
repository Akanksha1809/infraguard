"""Fixed, non-configurable identifiers that scope every lab operation.

These are deliberately hard-coded, not CLI flags or environment variables: the lab must
never be pointed at an arbitrary project name, container, or database, since that would
undermine the "never touch anything outside the lab" safety guarantee. The Postgres
credentials below are for a throwaway, localhost-only container with no real data in it —
not a secret worth protecting.
"""

from pathlib import Path

PROJECT_NAME = "infraguard-recovery-lab"
COMPOSE_FILE = Path(__file__).parents[5] / "docker" / "recovery_lab" / "docker-compose.yml"
SERVICE_NAME = "postgres"
CONTAINER_NAME = "infraguard-recovery-lab-postgres"

DB_USER = "infraguard"
DB_NAME = "infraguard_lab"
DB_PASSWORD = "infraguard-lab-only"  # noqa: S105 -- throwaway local-only lab container, not a real secret

TABLE_NAME = "orders"
SEED_ROW_COUNT = 50

STARTUP_TIMEOUT_SECONDS = 60
