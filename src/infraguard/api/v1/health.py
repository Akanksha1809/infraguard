from fastapi import APIRouter, Request

from infraguard.storage.db import get_schema_version

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> dict[str, str]:
    """Readiness: the database is reachable and has the expected schema."""
    settings = request.app.state.settings
    version = get_schema_version(settings.db_path)
    return {"status": "ok" if version is not None else "degraded", "schema_version": str(version)}
