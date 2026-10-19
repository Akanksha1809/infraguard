from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "change_analysis"


def _load(name: str) -> dict:
    import json

    return json.loads((FIXTURES_DIR / name).read_text())


def test_report_retrieval_round_trips_through_the_api(client: TestClient) -> None:
    analyze_response = client.post(
        "/api/v1/change-analysis/analyze", json={"plan": _load("no_op_and_read.json")}
    )
    assert analyze_response.status_code == 200
    run_id = analyze_response.json()["run_id"]

    report_response = client.get(f"/api/v1/reports/{run_id}")
    assert report_response.status_code == 200
    assert report_response.json()["run_id"] == run_id


def test_report_retrieval_404_for_unknown_run_id(client: TestClient) -> None:
    response = client.get("/api/v1/reports/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_reports_includes_recent_run(client: TestClient) -> None:
    analyze_response = client.post(
        "/api/v1/change-analysis/analyze", json={"plan": _load("no_op_and_read.json")}
    )
    run_id = analyze_response.json()["run_id"]

    list_response = client.get("/api/v1/reports")
    assert list_response.status_code == 200
    run_ids = [r["run_id"] for r in list_response.json()["runs"]]
    assert run_id in run_ids


def test_list_reports_filters_by_module(client: TestClient) -> None:
    client.post("/api/v1/change-analysis/analyze", json={"plan": _load("no_op_and_read.json")})

    response = client.get("/api/v1/reports", params={"module": "disaster_recovery"})
    assert response.status_code == 200
    assert response.json()["runs"] == []
