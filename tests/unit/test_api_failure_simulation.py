from pathlib import Path

import yaml
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "failure_simulation"


def _load(name: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / name).read_text())


def test_validate_topology_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/failure-simulation/validate-topology",
        json={"topology": _load("simple_chain.yaml")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inputs"]["component_count"] == 3


def test_validate_topology_endpoint_rejects_fatal_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/failure-simulation/validate-topology",
        json={"topology": _load("duplicate_ids.yaml")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "input_validation_error"


def test_simulate_failure_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/failure-simulation/simulate-failure",
        json={
            "topology": _load("simple_chain.yaml"),
            "scenario": {"failed_component_ids": ["c"]},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inputs"]["cascaded"] == ["a", "b"]


def test_simulate_failure_endpoint_rejects_missing_scenario(client: TestClient) -> None:
    response = client.post(
        "/api/v1/failure-simulation/simulate-failure",
        json={"topology": _load("simple_chain.yaml")},
    )
    assert response.status_code == 422
