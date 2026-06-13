"""Benchmark record schema and seed data for sales-calibration support."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from steam_publisher_predictor.models import SalesBreakdown

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


@dataclass
class BenchmarkRecord:
    """A single benchmark record representing a known game's analysis outcome."""

    game_name: str
    app_id: int
    release_date: str
    genre_cluster: str
    quality_score: float
    quality_confidence: float
    user_pool: int
    cl_score: float
    sales: float
    annual_long_tail_sales: float | None
    steam_score: float
    discussion_strength: float
    analyst_quality_score: float
    sao_anchor: float | None  # virtual ceiling, not a real sample
    source_label: str  # e.g. "official_release" or "calibration_seed"
    loaded_at: str  # ISO timestamp


@dataclass
class BenchmarkFile:
    """Envelope for a benchmark data file."""

    version: str
    loaded_at: str
    records: list[BenchmarkRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "loaded_at": self.loaded_at,
            "records": [asdict(r) for r in self.records],
        }

    @classmethod
    def from_dict(cls, data: dict) -> BenchmarkFile:
        records = [
            BenchmarkRecord(**{k: v for k, v in r.items()})
            for r in data.get("records", [])
        ]
        return cls(
            version=data.get("version", "v0.1"),
            loaded_at=data.get("loaded_at", ""),
            records=records,
        )


# ── Seed data ──────────────────────────────────────────────────────────────

_SEED_RECORDS: list[dict] = [
    {
        "game_name": "Balatro",
        "app_id": 2379780,
        "release_date": "2024-02-20",
        "genre_cluster": "Indie / Roguelike / Deck-building",
        "quality_score": 9.2,
        "quality_confidence": 0.88,
        "user_pool": 8_000_000,
        "cl_score": 2.45,
        "sales": 4_500_000,
        "annual_long_tail_sales": 1_200_000,
        "steam_score": 98.0,
        "discussion_strength": 8.5,
        "analyst_quality_score": 9.0,
        "sao_anchor": 6_000_000,
        "source_label": "official_release",
    },
    {
        "game_name": "Stardew Valley",
        "app_id": 413150,
        "release_date": "2016-02-26",
        "genre_cluster": "Simulation / Farming / Indie",
        "quality_score": 9.0,
        "quality_confidence": 0.95,
        "user_pool": 12_000_000,
        "cl_score": 2.20,
        "sales": 28_000_000,
        "annual_long_tail_sales": 3_500_000,
        "steam_score": 98.0,
        "discussion_strength": 7.8,
        "analyst_quality_score": 9.5,
        "sao_anchor": 40_000_000,
        "source_label": "official_release",
    },
    {
        "game_name": "Palworld",
        "app_id": 1623730,
        "release_date": "2024-01-19",
        "genre_cluster": "Survival / Monster-collection",
        "quality_score": 7.2,
        "quality_confidence": 0.82,
        "user_pool": 25_000_000,
        "cl_score": 2.60,
        "sales": 18_000_000,
        "annual_long_tail_sales": 2_000_000,
        "steam_score": 85.0,
        "discussion_strength": 9.5,
        "analyst_quality_score": 6.5,
        "sao_anchor": 30_000_000,
        "source_label": "official_release",
    },
    {
        "game_name": "Warm Snow",
        "app_id": 1059400,
        "release_date": "2021-01-28",
        "genre_cluster": "Souls-like / Indie / Action",
        "quality_score": 7.5,
        "quality_confidence": 0.75,
        "user_pool": 3_000_000,
        "cl_score": 1.80,
        "sales": 800_000,
        "annual_long_tail_sales": 100_000,
        "steam_score": 88.0,
        "discussion_strength": 5.0,
        "analyst_quality_score": 7.0,
        "sao_anchor": 1_500_000,
        "source_label": "official_release",
    },
    {
        "game_name": "Minecraft",
        "app_id": 0,
        "release_date": "2011-11-18",
        "genre_cluster": "Sandbox / Survival / Open-world",
        "quality_score": 8.5,
        "quality_confidence": 0.99,
        "user_pool": 170_000_000,
        "cl_score": 2.80,
        "sales": 300_000_000,
        "annual_long_tail_sales": 15_000_000,
        "steam_score": 92.0,
        "discussion_strength": 6.5,
        "analyst_quality_score": 8.0,
        "sao_anchor": 500_000_000,
        "source_label": "official_release",
    },
    {
        "game_name": "VS (Versus Mode)",
        "app_id": 0,
        "release_date": "2025-06-01",
        "genre_cluster": "Action / Indie / Competitive",
        "quality_score": 7.5,
        "quality_confidence": 0.60,
        "user_pool": 2_000_000,
        "cl_score": 1.75,
        "sales": 120_000,
        "annual_long_tail_sales": 20_000,
        "steam_score": 88.0,
        "discussion_strength": 4.5,
        "analyst_quality_score": 7.0,
        "sao_anchor": 200_000,
        "source_label": "calibration_seed",
    },
    {
        "game_name": "完蛋！我被美女包围了",
        "app_id": 2089440,
        "release_date": "2023-10-20",
        "genre_cluster": "Visual Novel / Romance / Drama",
        "quality_score": 6.0,
        "quality_confidence": 0.65,
        "user_pool": 18_000_000,
        "cl_score": 1.40,
        "sales": 1_200_000,
        "annual_long_tail_sales": 80_000,
        "steam_score": 85.0,
        "discussion_strength": 9.0,
        "analyst_quality_score": 5.5,
        "sao_anchor": 2_500_000,
        "source_label": "calibration_seed",
    },
]


def _dict_to_record(d: dict) -> BenchmarkRecord:
    return BenchmarkRecord(
        game_name=d["game_name"],
        app_id=d["app_id"],
        release_date=d["release_date"],
        genre_cluster=d["genre_cluster"],
        quality_score=d["quality_score"],
        quality_confidence=d["quality_confidence"],
        user_pool=d["user_pool"],
        cl_score=d["cl_score"],
        sales=d["sales"],
        annual_long_tail_sales=d.get("annual_long_tail_sales"),
        steam_score=d["steam_score"],
        discussion_strength=d["discussion_strength"],
        analyst_quality_score=d["analyst_quality_score"],
        sao_anchor=d.get("sao_anchor"),
        source_label=d["source_label"],
        loaded_at=d.get("loaded_at", datetime.now(timezone.utc).isoformat()),
    )


def save_benchmark_file(records: list[BenchmarkRecord], data_dir: Path | None = None) -> Path:
    """Save a complete benchmark file to data/benchmark_v0.1.json."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    file_obj = BenchmarkFile(version="v0.1", loaded_at=now, records=records)

    filepath = data_dir / "benchmark_v0.1.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(file_obj.to_dict(), f, indent=2, ensure_ascii=False)

    return filepath


def load_benchmark_file(data_dir: Path | None = None) -> BenchmarkFile | None:
    """Load the benchmark file from data/benchmark_v0.1.json."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    filepath = data_dir / "benchmark_v0.1.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BenchmarkFile.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def get_seed_records() -> list[BenchmarkRecord]:
    """Return the built-in seed records."""
    return [_dict_to_record(d) for d in _SEED_RECORDS]


# ── Comparison helpers ─────────────────────────────────────────────────────


@dataclass
class BenchmarkComparisonRow:
    """A single row in the benchmark comparison table."""

    benchmark_game: str
    quality_score: float
    quality_confidence: float  # fraction (0.0-1.0), not formatted string
    cl_score: float
    user_pool: int
    sales: int
    sao_anchor: float | None
    annual_long_tail_sales: float | None
    # Differences vs current result
    quality_diff: float
    cl_diff: float
    pool_diff: float
    sales_diff: float
    sao_diff: float | None


def compare_vs_benchmarks(
    sales_result: SalesBreakdown,
    benchmarks: list[BenchmarkRecord],
) -> list[BenchmarkComparisonRow]:
    """Compare current result against benchmark records.

    For each benchmark record, compute the difference between the
    benchmark's reference values and the current result's computed values.
    """
    current_cl = sales_result.cl_score
    current_quality = sales_result.quality.quality_score
    current_pool = sales_result.user_pool.estimated_user_pool
    current_sales = sales_result.sales

    rows: list[BenchmarkComparisonRow] = []
    for rec in benchmarks:
        rows.append(
            BenchmarkComparisonRow(
                benchmark_game=rec.game_name,
                quality_score=rec.quality_score,
                quality_confidence=rec.quality_confidence,
                cl_score=rec.cl_score,
                user_pool=rec.user_pool,
                sales=rec.sales,
                sao_anchor=rec.sao_anchor,
                annual_long_tail_sales=rec.annual_long_tail_sales,
                quality_diff=round(current_quality - rec.quality_score, 2),
                cl_diff=round(current_cl - rec.cl_score, 2),
                pool_diff=round(current_pool - rec.user_pool, 0),
                sales_diff=round(current_sales - rec.sales, 0),
                sao_diff=round(current_sales - (rec.sao_anchor or 0), 0) if rec.sao_anchor else None,
            )
        )
    return rows


def ensure_benchmark_exists(data_dir: Path | None = None) -> bool:
    """Create the benchmark file from seed data if it does not exist yet.
    Returns True if the file was just created.
    """
    if load_benchmark_file(data_dir) is not None:
        return False
    seed = get_seed_records()
    save_benchmark_file(seed, data_dir)
    return True
