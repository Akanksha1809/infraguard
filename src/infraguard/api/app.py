from fastapi import FastAPI
from fastapi.responses import JSONResponse

from infraguard.api.v1 import change_analysis, disaster_recovery, failure_simulation, health, policy, reports
from infraguard.config import Settings, get_settings
from infraguard.errors import InfraGuardError
from infraguard.logging_config import configure_logging
from infraguard.storage.db import init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    init_db(settings.db_path)

    app = FastAPI(title="InfraGuard", version="0.1.0")
    app.state.settings = settings

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(change_analysis.router, prefix="/api/v1")
    app.include_router(failure_simulation.router, prefix="/api/v1")
    app.include_router(disaster_recovery.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(policy.router, prefix="/api/v1")

    @app.exception_handler(InfraGuardError)
    def handle_infraguard_error(_request, exc: InfraGuardError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    return app
