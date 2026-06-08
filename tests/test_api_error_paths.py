# Steve 2026/06/07 迭代创建 - API 错误路径测试

from fastapi.testclient import TestClient

from steam_publisher_predictor.api import create_app

app = create_app()
client = TestClient(app)


def test_invalid_query_returns_400():
    """Search with empty query should return 400."""
    response = client.get("/api/search", params={"query": ""})
    assert response.status_code == 400


def test_search_with_random_query():
    """Search with a random query should return valid response (may be empty)."""
    response = client.get("/api/search", params={"query": "xzy_nonexistent_random_q_12345"})
    # May succeed (returns items list) or fail if SteamClient errors
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        assert "items" in response.json()


def test_analyze_with_empty_request():
    """Empty POST to /analyze should return 422."""
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422


def test_api_invalid_json_request():
    """Invalid JSON in POST body should return 422."""
    response = client.post("/api/analyze", content=b"not json", headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_api_predict_not_found():
    """POST /predict should return 404 (endpoint doesn't exist)."""
    response = client.post("/api/predict", json={})
    assert response.status_code == 404


def test_record_load_nonexistent():
    """Loading a non-existent record should return 404."""
    response = client.post("/api/record/load", json={"record_id": "does-not-exist-uuid"})
    assert response.status_code == 404


def test_delete_record_nonexistent():
    """Deleting a non-existent record should return 404."""
    response = client.delete("/api/record/does-not-exist-uuid")
    assert response.status_code == 404
