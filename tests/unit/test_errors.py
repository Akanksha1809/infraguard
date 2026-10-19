from fastapi import FastAPI
from fastapi.testclient import TestClient

from infraguard.api.app import create_app
from infraguard.config import Settings
from infraguard.errors import InputValidationError, NotFoundError


def _app_with_test_route(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/_test/not-found")
    def _not_found() -> None:
        raise NotFoundError("run abc123 not found", details={"run_id": "abc123"})

    @app.get("/_test/invalid")
    def _invalid() -> None:
        raise InputValidationError("plan.json is missing required field 'resource_changes'")

    return app


def test_not_found_error_shape(settings: Settings) -> None:
    client = TestClient(_app_with_test_route(settings))
    response = client.get("/_test/not-found")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "run abc123 not found",
            "details": {"run_id": "abc123"},
        }
    }


def test_input_validation_error_shape(settings: Settings) -> None:
    client = TestClient(_app_with_test_route(settings))
    response = client.get("/_test/invalid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "input_validation_error"
