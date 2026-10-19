import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "change_analysis"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_analyze_endpoint_returns_report(client: TestClient) -> None:
    response = client.post(
        "/api/v1/change-analysis/analyze", json={"plan": _load("delete_database.json")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["module"] == "change_analysis"
    assert body["policy_decision"]["decision"] == "fail"
    assert len(body["findings"]) >= 1


def test_analyze_endpoint_rejects_missing_plan_field(client: TestClient) -> None:
    response = client.post("/api/v1/change-analysis/analyze", json={})
    assert response.status_code == 422


def test_analyze_endpoint_rejects_malformed_plan_root(client: TestClient) -> None:
    response = client.post(
        "/api/v1/change-analysis/analyze", json={"plan": {"resource_changes": "not-a-list"}}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "input_validation_error"


def test_analyze_endpoint_accepts_custom_policy(client: TestClient) -> None:
    response = client.post(
        "/api/v1/change-analysis/analyze",
        json={
            "plan": _load("delete_database.json"),
            "policy": {"fail_on_severity_at_or_above": "critical", "warn_on_severity_at_or_above": "low"},
        },
    )
    assert response.status_code == 200
    assert response.json()["policy_decision"]["decision"] == "fail"
