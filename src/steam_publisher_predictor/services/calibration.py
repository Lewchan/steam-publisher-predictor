"""Calibration page data — provides pre-defined seed games with editable parameters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from steam_publisher_predictor.models import (
    ManualInputs,
    SteamGame,
    SteamDbStats,
    SalesBreakdown,
    QualityBreakdown,
    UserPoolBreakdown,
    UserPoolMatch,
)

# ── Seed calibration games ────────────────────────────────────────────────

_SEED_GAMES: list[dict] = [
    {
        "id": "vs",
        "game_name": "VS (Versus Mode)",
        "genre_cluster": "Action / Indie / Competitive",
        "description": "独立竞技对抗类游戏，对标 Balatro 的 indie success story",
        "expected_sales_range": [50000, 200000],
        "expected_quality_range": [7.0, 8.0],
        "expected_cl_range": [1.5, 2.0],
        "expected_pool_range": [1000000, 3000000],
        "steam_score": 88.0,
        "analyst_notes": "对标 Balatro 的 indie success，需验证实际销售区间",
        "manual_inputs": {
            "art_base": 6.0, "gameplay_depth": 7.0, "scope": 6.0, "narrative": 4.0,
            "ip_factor": 0.15, "influencer_factor": 0.3, "exposure_base": 0.2,
            "intent_base": 0.25, "purchase_base": 0.3,
        },
        "priority": 1,
    },
    {
        "id": "wandian",
        "game_name": "完蛋！我被美女包围了",
        "genre_cluster": "Visual Novel / Romance / Drama",
        "description": "真人互动影像作品，市场现象级爆款",
        "expected_sales_range": [500000, 2000000],
        "expected_quality_range": [5.0, 7.0],
        "expected_cl_range": [1.0, 1.8],
        "expected_pool_range": [10000000, 30000000],
        "steam_score": 85.0,
        "analyst_notes": "非传统 Steam 游戏品类，销量受真人影视热度驱动",
        "manual_inputs": {
            "art_base": 4.0, "gameplay_depth": 3.0, "scope": 7.0, "narrative": 9.0,
            "ip_factor": 0.0, "influencer_factor": 0.8, "exposure_base": 0.4,
            "intent_base": 0.3, "purchase_base": 0.25,
        },
        "priority": 2,
    },
    {
        "id": "warm_snow",
        "game_name": "暖雪 (Warm Snow)",
        "genre_cluster": "Souls-like / Action Roguelike / Indie",
        "description": "国风动作 Roguelike 游戏，已有标杆记录",
        "expected_sales_range": [500000, 1500000],
        "expected_quality_range": [7.0, 8.0],
        "expected_cl_range": [1.5, 2.0],
        "expected_pool_range": [2000000, 5000000],
        "steam_score": 88.0,
        "analyst_notes": "标杆对比记录已存在，需验证模型准确度",
        "manual_inputs": {
            "art_base": 7.0, "gameplay_depth": 8.0, "scope": 5.0, "narrative": 5.0,
            "ip_factor": 0.3, "influencer_factor": 0.2, "exposure_base": 0.15,
            "intent_base": 0.2, "purchase_base": 0.3,
        },
        "priority": 3,
    },
    {
        "id": "stardew",
        "game_name": "星露谷物语 (Stardew Valley)",
        "genre_cluster": "Farming Sim / Life Sim / Indie",
        "description": "经典 Farming Sim 标杆，长效长尾销售代表",
        "expected_sales_range": [20000000, 35000000],
        "expected_quality_range": [8.5, 9.5],
        "expected_cl_range": [1.8, 2.5],
        "expected_pool_range": [15000000, 25000000],
        "steam_score": 98.0,
        "analyst_notes": "标杆对比记录已存在，品质与销量双高标杆",
        "manual_inputs": {
            "art_base": 8.0, "gameplay_depth": 9.0, "scope": 8.0, "narrative": 7.0,
            "ip_factor": 0.2, "influencer_factor": 0.1, "exposure_base": 0.25,
            "intent_base": 0.35, "purchase_base": 0.4,
        },
        "priority": 4,
    },
    {
        "id": "palworld",
        "game_name": "幻兽帕鲁 (Palworld)",
        "genre_cluster": "Survival / Monster-collection",
        "description": "现象级爆款，生存+宝可梦融合品类",
        "expected_sales_range": [10000000, 25000000],
        "expected_quality_range": [6.5, 8.0],
        "expected_cl_range": [2.0, 3.0],
        "expected_pool_range": [20000000, 40000000],
        "steam_score": 85.0,
        "analyst_notes": "标杆对比记录已存在，话题驱动型销售，质量中等但用户池极大",
        "manual_inputs": {
            "art_base": 5.5, "gameplay_depth": 7.0, "scope": 8.0, "narrative": 5.0,
            "ip_factor": 0.4, "influencer_factor": 0.9, "exposure_base": 0.5,
            "intent_base": 0.3, "purchase_base": 0.35,
        },
        "priority": 5,
    },
    {
        "id": "minecraft",
        "game_name": "Minecraft",
        "genre_cluster": "Sandbox / Survival / Open-world",
        "description": "史上销量最高的独立游戏，跨平台现象",
        "expected_sales_range": [200000000, 350000000],
        "expected_quality_range": [7.5, 9.0],
        "expected_cl_range": [2.5, 3.0],
        "expected_pool_range": [150000000, 200000000],
        "steam_score": 92.0,
        "analyst_notes": "标杆对比记录已存在，MC 跨平台销售，Steam 仅占一部分",
        "manual_inputs": {
            "art_base": 8.0, "gameplay_depth": 9.5, "scope": 9.0, "narrative": 6.0,
            "ip_factor": 0.9, "influencer_factor": 0.3, "exposure_base": 0.3,
            "intent_base": 0.3, "purchase_base": 0.35,
        },
        "priority": 6,
    },
    {
        "id": "balatro",
        "game_name": "Balatro",
        "genre_cluster": "Indie / Roguelike / Deck-building",
        "description": "当前项目标杆之一，roguelike deck-builder 现象级",
        "expected_sales_range": [3000000, 6000000],
        "expected_quality_range": [8.5, 9.5],
        "expected_cl_range": [2.0, 2.8],
        "expected_pool_range": [6000000, 12000000],
        "steam_score": 98.0,
        "analyst_notes": "标杆对比记录已存在，项目核心参考标杆",
        "manual_inputs": {
            "art_base": 7.0, "gameplay_depth": 8.0, "scope": 6.0, "narrative": 4.0,
            "ip_factor": 0.1, "influencer_factor": 0.5, "exposure_base": 0.3,
            "intent_base": 0.3, "purchase_base": 0.35,
        },
        "priority": 0,
    },
]


@dataclass
class CalibrationGame:
    """A calibration seed game with editable manual inputs and expected ranges."""
    id: str
    game_name: str
    genre_cluster: str
    description: str
    expected_sales_range: list
    expected_quality_range: list
    expected_cl_range: list
    expected_pool_range: list
    steam_score: float
    analyst_notes: str
    manual_inputs: dict
    priority: int


@dataclass
class CalibrationResult:
    """Calibration result for a single game."""
    game_id: str
    game_name: str
    manual_inputs: dict
    computed: dict
    deviation: dict  # how far from expected range
    timestamp: str


def get_seed_cal_games() -> list[CalibrationGame]:
    """Return the built-in seed calibration games, sorted by priority."""
    games = [CalibrationGame(**{**g, "manual_inputs": {**g["manual_inputs"]}}) for g in _SEED_GAMES]
    games.sort(key=lambda g: g.priority)
    return games


def run_calibration(
    cal_game: CalibrationGame,
    calculator_func=None,
) -> CalibrationResult:
    """Run a full sales calculation for a calibration game.

    Args:
        cal_game: The calibration seed game with manual inputs.
        calculator_func: Optional custom calculator function for testing.
                         Defaults to the real calculate_sales.
    """
    from steam_publisher_predictor.models import ManualInputs

    mi = ManualInputs(**cal_game.manual_inputs)

    # Create a minimal SteamGame for calculation
    game = SteamGame(
        app_id=0,
        name=cal_game.game_name,
        url="",
        genres=[],
        steam_tags=[],
        categories=[],
        supported_languages=[],
        price_usd=14.99,
        review_count=0,
        review_score=cal_game.steam_score,
        metacritic_score=0,
    )

    if calculator_func:
        result = calculator_func(game, mi)
    else:
        from steam_publisher_predictor.services.calculator import calculate_sales
        result = calculate_sales(game, mi)

    # Calculate deviations from expected ranges
    deviation = {}
    expected = cal_game.expected_sales_range
    deviation["sales_pct"] = _pct_diff(result.sales, (expected[0] + expected[1]) / 2)
    deviation["quality_pct"] = _pct_diff(result.quality.quality_score, (cal_game.expected_quality_range[0] + cal_game.expected_quality_range[1]) / 2)
    deviation["cl_pct"] = _pct_diff(result.cl_score, (cal_game.expected_cl_range[0] + cal_game.expected_cl_range[1]) / 2)
    deviation["pool_pct"] = _pct_diff(result.user_pool.estimated_user_pool, (cal_game.expected_pool_range[0] + cal_game.expected_pool_range[1]) / 2)

    return CalibrationResult(
        game_id=cal_game.id,
        game_name=cal_game.game_name,
        manual_inputs={k: float(v) if isinstance(v, float) else v for k, v in mi.__dict__.items()},
        computed={
            "sales": result.sales,
            "quality_score": result.quality.quality_score,
            "quality_confidence": result.quality.quality_confidence,
            "cl_score": result.cl_score,
            "cl_base": result.cl_base,
            "showmanship_effect": result.showmanship_effect,
            "brand_factor": result.brand_factor,
            "user_pool": result.user_pool.estimated_user_pool,
            "base_conversion": result.base_conversion,
        },
        deviation=deviation,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _pct_diff(actual: float, expected: float) -> float:
    """Calculate percentage difference from expected."""
    if expected == 0:
        return 0.0
    return round((actual - expected) / expected * 100, 1)


def save_calibration_results(results: list[CalibrationResult], data_dir: Path | None = None) -> Path:
    """Save calibration results to data/calibration_results.json."""
    from dataclasses import asdict
    data_dir = data_dir or _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    filepath = data_dir / "calibration_results.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
    return filepath


def load_calibration_results(data_dir: Path | None = None) -> list[CalibrationResult]:
    """Load calibration results from data/calibration_results.json."""
    data_dir = data_dir or _data_dir()
    filepath = data_dir / "calibration_results.json"
    if not filepath.exists():
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [CalibrationResult(**r) for r in data]
    except (json.JSONDecodeError, KeyError):
        return []


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "data"
