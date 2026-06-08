"""Tests for the benchmark comparison functionality."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from steam_publisher_predictor.models import (
    ManualInputs,
    QualityBreakdown,
    SalesBreakdown,
    SteamGame,
    UserPoolBreakdown,
)
from steam_publisher_predictor.services.benchmark import (
    BenchmarkComparisonRow,
    BenchmarkFile,
    BenchmarkRecord,
    compare_vs_benchmarks,
    ensure_benchmark_exists,
    get_seed_records,
    load_benchmark_file,
    save_benchmark_file,
)


def _make_sample_game() -> SteamGame:
    return SteamGame(
        app_id=12345,
        name="Sample Game",
        url="https://store.steampowered.com/app/12345/",
        genres=["Action", "Indie"],
        price_usd=19.99,
        review_count=5000,
        review_score=88.0,
        metacritic_score=82,
        release_date="2024-06-15",
    )


def _make_sample_result() -> SalesBreakdown:
    game = _make_sample_game()
    manual = ManualInputs()

    return SalesBreakdown(
        game=game,
        quality=QualityBreakdown(
            rating_strength=3.5,
            rating_confidence=0.7,
            proof_strength=2.0,
            discussion_count_signal=1.5,
            discussion_engagement_signal=1.0,
            discussion_sentiment_signal=1.2,
            discussion_strength=3.7,
            persistence_strength=2.5,
            analyst_adjustment=0.0,
            quality_score=7.8,
            quality_confidence=0.65,
        ),
        user_pool=UserPoolBreakdown(
            matches=[],
            weighted_genre_sum=5_000_000,
            overlap_adjustment=0.75,
            platform_fit=1.0,
            region_fit=1.0,
            price_fit=1.0,
            estimated_user_pool=3_500_000,
        ),
        manual_inputs=manual,
        cl_base_raw=1089.0,
        cl_base=0.0001089,
        amplification_tag_total=0.0,
        showmanship_raw=0.25,
        showmanship_effect=0.25,
        brand_factor=0.2,
        cl_raw=1.95,
        cl_score=1.95,
        base_conversion=0.015,
        sales=150_000,
        annual_long_tail_sales=None,
    )


def test_compare_vs_benchmarks_returns_correct_count() -> None:
    """Comparison should return one row per benchmark record."""
    result = _make_sample_result()
    benchmarks = get_seed_records()

    rows = compare_vs_benchmarks(result, benchmarks)
    assert len(rows) == 5
    assert all(isinstance(r, BenchmarkComparisonRow) for r in rows)


def test_compare_differences_are_computed() -> None:
    """Difference columns should reflect current minus benchmark."""
    result = _make_sample_result()
    result.sales = 5_000_000  # Set to known value
    result.cl_score = 2.5
    result.quality.quality_score = 8.5

    benchmarks = get_seed_records()
    rows = compare_vs_benchmarks(result, benchmarks)

    # Balatro: quality=9.2, cl=2.45, sales=4_500_000
    balatro = next(r for r in rows if r.benchmark_game == "Balatro")
    assert balatro.quality_diff == pytest.approx(8.5 - 9.2, abs=1e-9)  # -0.7
    assert balatro.cl_diff == pytest.approx(2.5 - 2.45, abs=1e-9)  # +0.05
    assert balatro.sales_diff == pytest.approx(5_000_000 - 4_500_000, abs=1)  # +500_000


def test_compare_sao_anchor_handling() -> None:
    """SAO difference should be None when benchmark has no SAO anchor."""
    result = _make_sample_result()
    result.sales = 1_000_000

    benchmarks = [
        BenchmarkRecord(
            game_name="With SAO",
            app_id=1,
            release_date="2024-01-01",
            genre_cluster="Test",
            quality_score=7.0,
            quality_confidence=0.5,
            user_pool=1_000_000,
            cl_score=1.0,
            sales=800_000,
            annual_long_tail_sales=None,
            steam_score=80.0,
            discussion_strength=5.0,
            analyst_quality_score=7.0,
            sao_anchor=1_200_000,
            source_label="test",
            loaded_at="2024-06-01T00:00:00+00:00",
        ),
        BenchmarkRecord(
            game_name="No SAO",
            app_id=2,
            release_date="2024-01-01",
            genre_cluster="Test",
            quality_score=7.0,
            quality_confidence=0.5,
            user_pool=1_000_000,
            cl_score=1.0,
            sales=800_000,
            annual_long_tail_sales=None,
            steam_score=80.0,
            discussion_strength=5.0,
            analyst_quality_score=7.0,
            sao_anchor=None,
            source_label="test",
            loaded_at="2024-06-01T00:00:00+00:00",
        ),
    ]

    rows = compare_vs_benchmarks(result, benchmarks)
    with_sao = next(r for r in rows if r.benchmark_game == "With SAO")
    no_sao = next(r for r in rows if r.benchmark_game == "No SAO")

    assert with_sao.sao_diff is not None
    assert no_sao.sao_diff is None


def test_compare_empty_benchmarks() -> None:
    """Comparison with empty benchmark list should return empty."""
    result = _make_sample_result()
    rows = compare_vs_benchmarks(result, [])
    assert rows == []


def test_compare_vs_loaded_benchmark_file(tmp_path: Path) -> None:
    """Integration: load from file, then compare."""
    seed = get_seed_records()
    save_benchmark_file(seed, data_dir=tmp_path)

    result = _make_sample_result()
    loaded = load_benchmark_file(data_dir=tmp_path)
    assert loaded is not None

    rows = compare_vs_benchmarks(result, loaded.records)
    assert len(rows) == 5

    # Verify Stardew Valley reference
    stardew = next(r for r in rows if r.benchmark_game == "Stardew Valley")
    assert stardew.user_pool == 12_000_000
    assert stardew.sales_diff == result.sales - 28_000_000
