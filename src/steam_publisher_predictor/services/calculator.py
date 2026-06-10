# Webber 2026/06/10 场景对比：场景化校准参数计算
from __future__ import annotations

from dataclasses import dataclass
from steam_publisher_predictor.models import ManualInputs, SalesBreakdown, SteamGame
from steam_publisher_predictor.services.quality import estimate_quality
from steam_publisher_predictor.services.user_pool import estimate_user_pool
from steam_publisher_predictor.settings import (
    CalibrationConfig,
    load_calibration_config,
)

AMPLIFICATION_WEIGHTS = {
    "sexual_or_gore": 1.0,
    "extreme_novelty": 0.8,
    "real_time_juice": 0.6,
    "systemic_interlock": 1.0,
    "complex_system": 0.6,
    "linear_experience": 0.2,
}

# Default constants used as fallback when cfg is not provided.
_DEFAULT_CL_BIAS = 0.15
_DEFAULT_CL_WEIGHTS = {
    "cl_base": 1.2,
    "showmanship": 0.55,
    "brand": 0.55,
    "quality": 0.55,
}


def calculate_sales(
    game: SteamGame,
    manual_inputs: ManualInputs,
    cfg: CalibrationConfig | None = None,
) -> SalesBreakdown:
    """Calculate sales with calibration parameters.

    Args:
        game: Fetched Steam game data.
        manual_inputs: Manual design inputs.
        cfg: Calibration configuration.  If ``None``, defaults are loaded
              from ``settings.py`` (same values as the previous constants).
    """
    if cfg is None:
        cfg = load_calibration_config()

    quality = estimate_quality(game, manual_inputs)
    user_pool = estimate_user_pool(game, manual_inputs)

    cl_base_raw = manual_inputs.art_base * (
        manual_inputs.gameplay_depth * manual_inputs.scope * manual_inputs.narrative
    ) ** 2
    cl_base = cl_base_raw / 10_000_000

    amplification_tag_total = sum(
        weight for field_name, weight in AMPLIFICATION_WEIGHTS.items() if getattr(manual_inputs, field_name)
    )
    showmanship_raw = (manual_inputs.art_base * manual_inputs.narrative) / 100 * (1 + amplification_tag_total)
    showmanship_effect = min(cfg.showmanship_cap, showmanship_raw)
    brand_factor = manual_inputs.ip_factor * 0.5 + manual_inputs.influencer_factor * 0.5

    cl_bias = _DEFAULT_CL_BIAS
    cl_weights = _DEFAULT_CL_WEIGHTS

    cl_raw = (
        cl_bias
        + cl_weights["cl_base"] * cl_base
        + cl_weights["showmanship"] * (showmanship_effect / cfg.showmanship_cap if showmanship_effect else 0.0)
        + cl_weights["brand"] * brand_factor
        + cl_weights["quality"] * (quality.quality_score / 10.0)
    )
    cl_score = min(cfg.cl_cap, max(0.0, cl_raw))

    base_conversion = manual_inputs.exposure_base * manual_inputs.intent_base * manual_inputs.purchase_base
    sales = user_pool.estimated_user_pool * base_conversion * (1 + cl_score) ** 3

    annual_long_tail_sales = None
    if manual_inputs.peak_dau > 0 and manual_inputs.median_line > 0:
        annual_long_tail_sales = manual_inputs.peak_dau * manual_inputs.median_line * 40

    return SalesBreakdown(
        game=game,
        quality=quality,
        user_pool=user_pool,
        manual_inputs=manual_inputs,
        cl_base_raw=cl_base_raw,
        cl_base=cl_base,
        amplification_tag_total=amplification_tag_total,
        showmanship_raw=showmanship_raw,
        showmanship_effect=showmanship_effect,
        brand_factor=brand_factor,
        cl_raw=cl_raw,
        cl_score=cl_score,
        base_conversion=base_conversion,
        sales=sales,
        annual_long_tail_sales=annual_long_tail_sales,
    )


@dataclass
class ScenarioCalibration:
    """Per-scenario calibration overrides applied on top of the base config."""
    name: str
    cl_cap: float = 3.0
    cl_k1: float = 2.0
    cl_k2: float = 2.0
    quality_bias: float = 0.0  # shift applied to quality_score after calculation


SCENARIO_CONFIGS: dict[str, ScenarioCalibration] = {
    "conservative": ScenarioCalibration(
        name="Conservative",
        cl_cap=1.5,
        cl_k1=1.5,
        cl_k2=1.0,
        quality_bias=-0.5,
    ),
    "baseline": ScenarioCalibration(
        name="Baseline",
        cl_cap=3.0,
        cl_k1=2.0,
        cl_k2=2.0,
        quality_bias=0.0,
    ),
    "optimistic": ScenarioCalibration(
        name="Optimistic",
        cl_cap=4.0,
        cl_k1=2.5,
        cl_k2=3.0,
        quality_bias=0.5,
    ),
}


def calculate_sales_with_scenario(
    game: SteamGame,
    manual_inputs: ManualInputs,
    scenario: str = "baseline",
    cfg: CalibrationConfig | None = None,
) -> SalesBreakdown:
    """Calculate sales with scenario-specific calibration overrides.

    Args:
        game: Fetched Steam game data.
        manual_inputs: Manual design inputs.
        scenario: One of 'conservative', 'baseline', 'optimistic'.
        cfg: Base calibration config.  If None, defaults are loaded.

    Returns:
        SalesBreakdown with scenario overrides applied.
    """
    if cfg is None:
        cfg = load_calibration_config()

    scenario_cfg = SCENARIO_CONFIGS.get(scenario, SCENARIO_CONFIGS["baseline"])

    # Create a modified calibration config with scenario overrides
    scenario_cfg_obj = CalibrationConfig(
        rating_weight=cfg.rating_weight,
        proof_weight=cfg.proof_weight,
        discussion_weight=cfg.discussion_weight,
        persistence_weight=cfg.persistence_weight,
        showmanship_cap=cfg.showmanship_cap,
        cl_cap=scenario_cfg.cl_cap,
        cl_k1=scenario_cfg.cl_k1,
        cl_k2=scenario_cfg.cl_k2,
        low_confidence_threshold=cfg.low_confidence_threshold,
        medium_confidence_threshold=cfg.medium_confidence_threshold,
        missing_source_threshold=cfg.missing_source_threshold,
    )

    result = calculate_sales(game, manual_inputs, cfg=scenario_cfg_obj)

    # Apply quality bias to the result
    if scenario_cfg.quality_bias != 0.0:
        result.quality.quality_score = max(
            0, min(10, result.quality.quality_score + scenario_cfg.quality_bias)
        )

    return result
