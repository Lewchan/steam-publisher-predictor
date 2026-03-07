from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from steam_publisher_predictor.models import ManualInputs
from steam_publisher_predictor.services.calculator import calculate_sales
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1)
    manual_inputs: dict[str, object] | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Steam Publisher Predictor API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/search")
    def search(query: str) -> dict[str, object]:
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query is required.")

        client = _create_client()
        try:
            return {"items": client.search(query)}
        except SteamClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/analyze")
    def analyze(payload: AnalyzeRequest) -> dict[str, object]:
        client = _create_client()
        manual_inputs = ManualInputs(**(payload.manual_inputs or {}))

        try:
            game = client.fetch_game(payload.query)
            result = calculate_sales(game, manual_inputs)
        except SteamClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "query": payload.query,
            "game": asdict(game),
            "analysis": asdict(result),
        }

    return app


def _create_client() -> SteamClient:
    return SteamClient()


app = create_app()
