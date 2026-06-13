from __future__ import annotations

import time

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
from steam_publisher_predictor.services.calculator import (
    calculate_sales,
    calculate_sales_with_scenario,
    SCENARIO_CONFIGS,
)
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError
from steam_publisher_predictor.services.storage import record as storage
from steam_publisher_predictor.services import benchmark as benchmark_service
from steam_publisher_predictor.services import calibration as cal_service
from steam_publisher_predictor.services.discussion_source_base import (
    list_registered_sources,
    get_discussion_source,
)
from steam_publisher_predictor.services.discussion_source_base import (
    NormalizedDiscussionResult,
)


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1)
    manual_inputs: dict[str, object] | None = None
    save_record: bool = False


class RecordLoadRequest(BaseModel):
    record_id: str = Field(min_length=1)


class ScenarioRequest(BaseModel):
    query: str = Field(min_length=1)
    manual_inputs: dict[str, object] | None = None


# ── Benchmark compare helper (extracted to eliminate inline class duplication) ──


def _build_sales_result_from_dict(sales_result: dict) -> object:
    """Build a minimal SalesBreakdown-like object from a dict payload.

    Used by the benchmark_compare endpoint to adapt JSON payloads into
    the structure expected by benchmark_service.compare_vs_benchmarks().
    """
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

    return _SalesResult()


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
        if bf is None:
            return {"comparison": [], "message": "No benchmark data"}

        sales_obj = _build_sales_result_from_dict(sales_result)
        records = [benchmark_service._dict_to_record(r) for r in bf.records]
        comparison = benchmark_service.compare_vs_benchmarks(sales_obj, records)
        return {
            "comparison": [asdict(r) for r in comparison],
            "benchmarks": bf.to_dict(),
        }

    @app.get("/api/steamdb")
    def get_steamdb(app_id: int) -> dict[str, object]:
        """Fetch SteamDB stats for a given app_id."""
        client = SteamClient()
        try:
            game = client.fetch_game(str(app_id))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Steam fetch failed: {exc}") from exc

        if game.app_id == 0:
            raise HTTPException(status_code=404, detail="Game not found")

        try:
            from steam_publisher_predictor.services.steamdb_client import (
                SteamDbClient,
                SteamDbClientError,
            )
            db_client = SteamDbClient()
            db_stats = db_client.fetch_stats(game.app_id)
            game.steamdb = db_stats
            response: dict[str, object] = {"game": asdict(game), "steamdb": asdict(db_stats)}
            return response
        except SteamDbClientError as exc:
            return {
                "game": asdict(game),
                "steamdb": None,
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "game": asdict(game),
                "steamdb": None,
                "error": f"SteamDB fetch failed: {exc}",
            }

    @app.get("/api/steamdb_batch")
    def get_steamdb_batch(app_ids: str) -> dict[str, object]:
        """Fetch SteamDB stats for multiple app_ids (comma-separated).

        Enhanced error handling with categorized failures:
        - "rate_limit": HTTP 429 or retry-after detected (transient)
        - "not_found": Game does not exist on Steam (permanent)
        - "blocked": SteamDB blocked IP/bot detection (transient)
        - "timeout": Request timeout (transient)
        - "network": DNS/connectivity failure (transient)
        - "other": Unknown error
        """
        ids = [int(a.strip()) for a in app_ids.split(",") if a.strip()]
        if not ids:
            return {"results": [], "errors": [], "message": "No valid app_ids provided"}

        results: list[dict] = []
        errors: list[dict] = []
        error_categories: dict[str, int] = {}

        try:
            from steam_publisher_predictor.services.steamdb_client import (
                SteamDbClient,
                SteamDbClientError,
            )
            from steam_publisher_predictor.services.steamdb_http import (
                SteamDbHttpClientError,
            )
            import httpx

            db_client = SteamDbClient()

            for idx, aid in enumerate(ids):
                # Add inter-request delay for batch calls to avoid rate limiting
                if idx > 0:
                    time.sleep(2.0)

                try:
                    stats = db_client.fetch_stats(aid)
                    if stats.has_data:
                        results.append({
                            "app_id": aid,
                            "stats": {
                                "current_players": stats.current_players,
                                "peak_24h": stats.peak_24h,
                                "all_time_peak": stats.all_time_peak,
                                "followers": stats.followers,
                                "reviews": stats.reviews,
                                "steamdb_rating": stats.steamdb_rating,
                                "positive_reviews": stats.positive_reviews,
                                "negative_reviews": stats.negative_reviews,
                                "daily_active_users_rank": stats.daily_active_users_rank,
                                "top_sellers_rank": stats.top_sellers_rank,
                                "wishlist_activity_rank": stats.wishlist_activity_rank,
                                "last_30_days_peak": stats.last_30_days_peak,
                            },
                        })
                    else:
                        error_categories.setdefault("no_data", 0)
                        error_categories["no_data"] += 1
                        errors.append({
                            "app_id": aid,
                            "error": "SteamDB page has no chart data (game may be too new)",
                            "error_category": "no_data",
                            "transient": True,
                        })
                except SteamDbHttpClientError as exc:
                    msg = str(exc).lower()
                    if "banned" in msg or "blocked" in msg:
                        cat = "blocked"
                    elif "bot" in msg or "cloudflare" in msg or "challenge" in msg:
                        cat = "blocked"
                    else:
                        cat = "other"
                    error_categories.setdefault(cat, 0)
                    error_categories[cat] += 1
                    errors.append({
                        "app_id": aid,
                        "error": str(exc),
                        "error_category": cat,
                        "transient": cat in ("blocked",),
                    })
                except SteamDbClientError as exc:
                    msg = str(exc).lower()
                    if "banned" in msg or "blocked" in msg or "bot" in msg:
                        cat = "blocked"
                    elif "timeout" in msg:
                        cat = "timeout"
                    else:
                        cat = "other"
                    error_categories.setdefault(cat, 0)
                    error_categories[cat] += 1
                    errors.append({
                        "app_id": aid,
                        "error": str(exc),
                        "error_category": cat,
                        "transient": cat in ("blocked", "timeout"),
                    })
                except httpx.HTTPStatusError as exc:
                    cat = "rate_limit" if exc.response.status_code == 429 else "network"
                    error_categories.setdefault(cat, 0)
                    error_categories[cat] += 1
                    errors.append({
                        "app_id": aid,
                        "error": f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}",
                        "error_category": cat,
                        "transient": cat == "rate_limit",
                    })
                except httpx.ConnectError as exc:
                    error_categories.setdefault("network", 0)
                    error_categories["network"] += 1
                    errors.append({
                        "app_id": aid,
                        "error": f"Network error: {exc}",
                        "error_category": "network",
                        "transient": True,
                    })
                except httpx.TimeoutException as exc:
                    error_categories.setdefault("timeout", 0)
                    error_categories["timeout"] += 1
                    errors.append({
                        "app_id": aid,
                        "error": f"Request timeout: {exc}",
                        "error_category": "timeout",
                        "transient": True,
                    })
                except Exception as exc:
                    error_categories.setdefault("other", 0)
                    error_categories["other"] += 1
                    errors.append({
                        "app_id": aid,
                        "error": f"Unexpected error: {exc}",
                        "error_category": "other",
                        "transient": False,
                    })

        except Exception as exc:
            return {"results": results, "errors": errors, "message": f"Unexpected error: {exc}"}

        summary = {
            "total_requested": len(ids),
            "successful": len(results),
            "failed": len(errors),
            "categories": error_categories,
        }

        return {
            "results": results,
            "errors": errors,
            "summary": summary,
            "error_categories": error_categories,
        }

    # ── Discussion Data API ──────────────────────────────────────────────

    @app.get("/api/discussion_sources")
    def list_discussion_sources() -> dict[str, object]:
        """Return all registered discussion source types."""
        return {"sources": list_registered_sources()}

    @app.post("/api/discussion")
    def fetch_discussion_data(payload: dict[str, object] = {}) -> dict[str, object]:
        """Fetch discussion data for a game across all registered sources.

        Returns normalised discussion results per source, following
        Iteration_Development_Spec §15 (Data Adapter Rules).
        """
        game_name = payload.get("game_name", "")
        max_results = payload.get("max_results", 20)
        if not game_name:
            return {"results": [], "message": "game_name is required"}

        sources = list_registered_sources()
        results = []
        for source_type in sources:
            source_cls = get_discussion_source(source_type)
            if source_cls is None:
                continue
            try:
                source_instance = source_cls()
                normalized = source_instance.fetch(game_name, max_results=max_results)
                results.append(asdict(normalized))
            except Exception as exc:
                # Never crash — return error message
                results.append({
                    "source_type": source_type,
                    "game_name": game_name,
                    "error_message": f"Unexpected error: {exc}",
                })

        return {"results": results, "sources": sources}

    # ── Scenario Comparison API ──────────────────────────────────────────

    @app.get("/api/scenarios")
    def list_scenarios() -> dict[str, object]:
        """Return available scenario configurations."""
        return {
            "scenarios": [
                {
                    "name": cfg.name,
                    "cl_cap": cfg.cl_cap,
                    "cl_k1": cfg.cl_k1,
                    "cl_k2": cfg.cl_k2,
                    "quality_bias": cfg.quality_bias,
                }
                for cfg in SCENARIO_CONFIGS.values()
            ]
        }

    @app.post("/api/scenarios")
    def run_scenario_comparison(payload: ScenarioRequest) -> dict[str, object]:
        """Run scenario comparison for a given game query.

        Returns all three scenarios (conservative, baseline, optimistic)
        with their respective calibration overrides applied.
        """
        client = _create_client()
        manual_inputs = ManualInputs(**(payload.manual_inputs or {}))

        try:
            game = client.fetch_game(payload.query)
        except SteamClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        results = {}
        for scenario_name in SCENARIO_CONFIGS:
            try:
                breakdown = calculate_sales_with_scenario(
                    game, manual_inputs, scenario=scenario_name
                )
                results[scenario_name] = {
                    "game": asdict(game),
                    "scenario": SCENARIO_CONFIGS[scenario_name].name,
                    "analysis": asdict(breakdown),
                }
            except Exception as exc:
                results[scenario_name] = {"error": str(exc)}

        return {"query": payload.query, "scenarios": results}

    # ── Calibration API ──────────────────────────────────────────────────

    @app.get("/api/cal_games")
    def list_cal_games() -> dict[str, object]:
        """Return calibration seed games for the calibration page."""
        games = cal_service.get_seed_cal_games()
        return {"games": [asdict(g) for g in games]}

    @app.post("/api/calibrate")
    def run_calibration(payload: dict[str, object] = {}) -> dict[str, object]:
        """Run calibration for one or all seed games."""
        game_ids = payload.get("game_ids")  # None = all
        results = []
        for cal_game in cal_service.get_seed_cal_games():
            if game_ids is not None and cal_game.id not in game_ids:
                continue
            result = cal_service.run_calibration(cal_game)
            results.append(asdict(result))
        # Save results
        cal_results = [cal_service.CalibrationResult(**r) for r in results]
        cal_service.save_calibration_results(cal_results)
        return {"results": results}

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
