from pathlib import Path

import yaml
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "disaster_recovery"


def _load(name: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / name).read_text())


def test_assess_recovery_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/disaster-recovery/assess-recovery",
        json={
            "policy": _load("policy_valid.yaml"),
            "evidence": _load("evidence_valid.json"),
            "as_of": "2026-10-19T12:00:00Z",
        },
    )
    assert response.status_code == 200
    body = response.json()
    readiness = {r["workload_id"]: r for r in body["inputs"]["readiness"]}
    assert readiness["wl"]["overall"] == "ready"


def test_assess_recovery_endpoint_rejects_fatal_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/disaster-recovery/assess-recovery",
        json={"policy": _load("policy_duplicate.yaml"), "evidence": _load("evidence_valid.json")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "input_validation_error"


def test_assess_recovery_endpoint_rejects_missing_fields(client: TestClient) -> None:
    response = client.post("/api/v1/disaster-recovery/assess-recovery", json={})
    assert response.status_code == 422
