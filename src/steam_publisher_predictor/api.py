from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from steam_publisher_predictor.models import ManualInputs
from steam_publisher_predictor.settings import (
    CalibrationUpdate,
    CalibrationConfig,
    load_calibration_config,
    save_calibration_config,
    get_allowed_origins,
)
from steam_publisher_predictor.services.calculator import calculate_sales
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError
from steam_publisher_predictor.services.storage import record as storage
from steam_publisher_predictor.services import benchmark as benchmark_service


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1)
    manual_inputs: dict[str, object] | None = None
    save_record: bool = False


class RecordLoadRequest(BaseModel):
    record_id: str = Field(min_length=1)


def create_app() -> FastAPI:
    app = FastAPI(title="Steam Publisher Predictor API", version="0.1.0")
    allowed_origins = get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "allowed_origins": allowed_origins}

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

        response: dict[str, object] = {
            "query": payload.query,
            "game": asdict(game),
            "analysis": asdict(result),
        }

        if payload.save_record:
            try:
                filepath = storage.save_prediction_record(result, payload.query)
                response["saved_record_path"] = str(filepath)
            except Exception as exc:
                response["save_error"] = str(exc)

        return response

    @app.post("/api/record/load")
    def load_record(payload: RecordLoadRequest) -> dict[str, object]:
        data = storage.load_record(payload.record_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Record not found.")
        return {"record": data}

    @app.get("/api/records")
    def list_records(limit: int = 50) -> dict[str, object]:
        records = storage.list_records(limit=limit)
        return {"records": records}

    @app.delete("/api/record/{record_id}")
    def delete_record(record_id: str) -> dict[str, object]:
        deleted = storage.delete_record(record_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Record not found.")
        return {"deleted": True}

    @app.get("/api/benchmarks")
    def list_benchmarks() -> dict[str, object]:
        """Return benchmark reference data for frontend comparison."""
        benchmark_service.ensure_benchmark_exists()
        bf = benchmark_service.load_benchmark_file()
        if bf is None:
            return {"records": [], "version": "v0.1", "loaded_at": "", "message": "No benchmark data"}
        return bf.to_dict()

    @app.post("/api/benchmark_compare")
    def benchmark_compare(payload: dict[str, object] = {}) -> dict[str, object]:
        """Compare a sales result against all benchmark records."""
        sales_result = payload.get("analysis", {})
        if not sales_result:
            return {"comparison": [], "message": "No analysis data provided"}
        benchmark_service.ensure_benchmark_exists()
        bf = benchmark_service.load_benchmark_file()
        from dataclasses import asdict
        from steam_publisher_predictor.models import SalesBreakdown
        if bf is None:
            return {"comparison": [], "message": "No benchmark data"}

        # Build a minimal SalesBreakdown-like structure for comparison
        quality_data = sales_result.get("quality", {})
        user_pool_data = sales_result.get("user_pool", {})

        class _Quality:
            quality_score = quality_data.get("quality_score", 0)
            quality_confidence = quality_data.get("quality_confidence", 0)
            rating_strength = quality_data.get("rating_strength", 0)
            rating_confidence = quality_data.get("rating_confidence", 0)
            proof_strength = quality_data.get("proof_strength", 0)
            discussion_count_signal = quality_data.get("discussion_count_signal", 0)
            discussion_engagement_signal = quality_data.get("discussion_engagement_signal", 0)
            discussion_sentiment_signal = quality_data.get("discussion_sentiment_signal", 0)
            discussion_strength = quality_data.get("discussion_strength", 0)
            persistence_strength = quality_data.get("persistence_strength", 0)
            analyst_adjustment = quality_data.get("analyst_adjustment", 0)
            missing_quality_sources = quality_data.get("missing_quality_sources", [])

        class _UserPool:
            estimated_user_pool = user_pool_data.get("estimated_user_pool", 0)
            weighted_genre_sum = user_pool_data.get("weighted_genre_sum", 0)
            overlap_adjustment = user_pool_data.get("overlap_adjustment", 0)
            platform_fit = user_pool_data.get("platform_fit", 0)
            region_fit = user_pool_data.get("region_fit", 0)
            price_fit = user_pool_data.get("price_fit", 0)
            matches = user_pool_data.get("matches", [])

        class _SalesResult:
            sales = sales_result.get("sales", 0)
            cl_score = sales_result.get("cl_score", 0)
            quality = _Quality()
            user_pool = _UserPool()

        records = [benchmark_service._dict_to_record(r) for r in bf.records]
        comparison = benchmark_service.compare_vs_benchmarks(_SalesResult(), records)
        return {
            "comparison": [asdict(r) for r in comparison],
            "benchmarks": bf.to_dict(),
        }

    # ── Calibration API ──────────────────────────────────────────────────

    @app.get("/api/calibration")
    def get_calibration() -> dict[str, object]:
        """Return current server-side calibration configuration.

        Validates persisted weights sum to 1.0 and warns if not.
        """
        cfg = load_calibration_config()
        from dataclasses import asdict

        # Validate persisted weights
        weight_total = (
            cfg.rating_weight + cfg.proof_weight + cfg.discussion_weight + cfg.persistence_weight
        )
        warning = None
        if abs(weight_total - 1.0) > 0.01:
            warning = (
                f"Persisted quality weights sum to {weight_total:.4f} (expected 1.0). "
                "This may cause unexpected calculation results."
            )

        result: dict[str, object] = {"calibration": asdict(cfg)}
        if warning:
            result["warning"] = warning
        return result

    @app.put("/api/calibration")
    def update_calibration(payload: CalibrationUpdate) -> dict[str, object]:
        """Update calibration configuration with provided fields.

        Weights are validated by the Pydantic model before reaching here.
        The full persisted config is validated after merge.
        """
        cfg = load_calibration_config()
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update.")
        for key, value in update_data.items():
            setattr(cfg, key, value)

        # Post-merge validation: check all four weights if any were updated
        weight_keys = ("rating_weight", "proof_weight", "discussion_weight", "persistence_weight")
        provided_in_update = {k for k in update_data if k in weight_keys}
        if len(provided_in_update) == 4 or (
            len(provided_in_update) >= 1
            and all(getattr(cfg, k) is not None for k in weight_keys)
        ):
            total = sum(getattr(cfg, k) for k in weight_keys)
            if abs(total - 1.0) > 0.01:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Quality weight proportions must sum to 1.0 (got {total:.4f}). "
                        "Current config after merge: "
                        + ", ".join(f"{k}={getattr(cfg, k)}" for k in weight_keys)
                    ),
                )

        save_calibration_config(cfg)
        from dataclasses import asdict
        return {"calibration": asdict(cfg)}

    return app


def _create_client() -> SteamClient:
    return SteamClient()


app = create_app()
