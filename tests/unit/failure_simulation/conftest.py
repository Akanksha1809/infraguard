from pathlib import Path

import pytest
import yaml

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "failure_simulation"
EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples" / "topologies"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return yaml.safe_load((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture
def fixture_path():
    def _path(name: str) -> Path:
        return FIXTURES_DIR / name

    return _path


@pytest.fixture
def load_example():
    def _load(name: str) -> dict:
        return yaml.safe_load((EXAMPLES_DIR / name).read_text())

    return _load


@pytest.fixture
def example_path():
    def _path(name: str) -> Path:
        return EXAMPLES_DIR / name

    return _path
