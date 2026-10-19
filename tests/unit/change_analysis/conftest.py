import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "change_analysis"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture
def fixture_path():
    def _path(name: str) -> Path:
        return FIXTURES_DIR / name

    return _path
