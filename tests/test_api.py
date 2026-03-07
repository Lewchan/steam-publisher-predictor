from dataclasses import asdict

from fastapi.testclient import TestClient

from steam_publisher_predictor.api import create_app
from steam_publisher_predictor.models import ManualInputs, SteamDbStats, SteamGame
from steam_publisher_predictor.services.calculator import calculate_sales


class FakeSteamClient:
    def search(self, query: str):
        return [{"app_id": 42, "name": "Example Game", "price_usd": 19.99}]

    def fetch_game(self, query: str) -> SteamGame:
        return SteamGame(
            app_id=42,
            name="Example Game",
            url="https://store.steampowered.com/app/42/",
            developer_names=["Studio"],
            publisher_names=["Publisher"],
            genres=["Action RPG", "Open World"],
            steam_tags=["Open World", "Survival", "Anime"],
            categories=["Single-player"],
            supported_languages=["English", "Chinese"],
            price_usd=19.99,
            review_count=12345,
            review_score=8.8,
            metacritic_score=80,
            release_date="2025-01-01",
            short_description="Example description.",
            steamdb=SteamDbStats(url="https://steamdb.info/app/42/charts/", unavailable_reason="SteamDB blocked this IP address."),
        )


def test_health_endpoint_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "allowed_origins" in response.json()


def test_search_endpoint_returns_items(monkeypatch) -> None:
    app = create_app()
    monkeypatch.setattr("steam_publisher_predictor.api._create_client", lambda: FakeSteamClient())
    client = TestClient(app)

    response = client.get("/api/search", params={"query": "Example"})

    assert response.status_code == 200
    assert response.json()["items"][0]["app_id"] == 42


def test_analyze_endpoint_returns_game_and_analysis(monkeypatch) -> None:
    app = create_app()
    monkeypatch.setattr("steam_publisher_predictor.api._create_client", lambda: FakeSteamClient())
    client = TestClient(app)

    response = client.post(
        "/api/analyze",
        json={"query": "Example", "manual_inputs": {"art_base": 8, "gameplay_depth": 7, "scope": 6, "narrative": 5}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["game"]["app_id"] == 42
    assert body["analysis"]["sales"] > 0
