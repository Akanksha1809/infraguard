from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infraguard.api.app import create_app
from infraguard.config import Settings


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "infraguard-test.db"


@pytest.fixture
def settings(db_path: Path) -> Settings:
    return Settings(db_path=db_path, log_level="DEBUG")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    return TestClient(app)
