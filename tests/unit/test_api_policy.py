from fastapi.testclient import TestClient


def test_policy_endpoint_returns_default_policy_and_rules(client: TestClient) -> None:
    response = client.get("/api/v1/policy")
    assert response.status_code == 200
    body = response.json()
    assert body["change_analysis_default_policy"]["fail_on_severity_at_or_above"] == "high"
    rule_ids = {r["rule_id"] for r in body["rules"]}
    assert "destructive_delete" in rule_ids
    assert "single_point_of_failure" in rule_ids
    assert "no_restore_test" in rule_ids
