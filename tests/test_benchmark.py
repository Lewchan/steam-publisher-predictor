"""Tests for the benchmark module."""

from __future__ import annotations

from pathlib import Path
import tempfile

from steam_publisher_predictor.services.benchmark import (
    BenchmarkFile,
    BenchmarkRecord,
    get_seed_records,
    load_benchmark_file,
    save_benchmark_file,
    ensure_benchmark_exists,
)


def test_seed_records_count() -> None:
    records = get_seed_records()
    assert len(records) == 5

    names = {r.game_name for r in records}
    assert names == {"Balatro", "Stardew Valley", "Palworld", "Warm Snow", "Minecraft"}


def test_seed_record_fields() -> None:
    records = get_seed_records()
    record = next(r for r in records if r.game_name == "Balatro")

    assert record.app_id == 2379780
    assert record.genre_cluster == "Indie / Roguelike / Deck-building"
    assert record.quality_score == 9.2
    assert record.user_pool == 8_000_000
    assert record.sales == 4_500_000
    assert record.sao_anchor == 6_000_000
    assert record.source_label == "official_release"


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    records = get_seed_records()
    path = save_benchmark_file(records, data_dir=tmp_path)

    assert path.exists()
    loaded = load_benchmark_file(data_dir=tmp_path)
    assert loaded is not None
    assert loaded.version == "v0.1"
    assert len(loaded.records) == 5

    first = loaded.records[0]
    assert first.game_name == "Balatro"
    assert first.cl_score == 2.45


def test_load_nonexistent_returns_none(tmp_path: Path) -> None:
    loaded = load_benchmark_file(data_dir=tmp_path)
    assert loaded is None


def test_ensure_benchmark_creates_when_missing(tmp_path: Path) -> None:
    result = ensure_benchmark_exists(data_dir=tmp_path)
    assert result is True
    assert (tmp_path / "benchmark_v0.1.json").exists()

    # Second call should not recreate
    result2 = ensure_benchmark_exists(data_dir=tmp_path)
    assert result2 is False


def test_benchmark_file_serialization() -> None:
    records = [
        BenchmarkRecord(
            game_name="Test Game",
            app_id=123,
            release_date="2024-01-01",
            genre_cluster="Test",
            quality_score=7.0,
            quality_confidence=0.5,
            user_pool=1_000_000,
            cl_score=1.5,
            sales=500_000,
            annual_long_tail_sales=50_000,
            steam_score=90.0,
            discussion_strength=6.0,
            analyst_quality_score=7.0,
            sao_anchor=800_000,
            source_label="calibration_seed",
            loaded_at="2024-06-01T00:00:00+00:00",
        ),
    ]
    file_obj = BenchmarkFile(version="v0.2", loaded_at="2024-06-01T00:00:00+00:00", records=records)
    data = file_obj.to_dict()

    assert data["version"] == "v0.2"
    assert len(data["records"]) == 1
    assert data["records"][0]["game_name"] == "Test Game"

    restored = BenchmarkFile.from_dict(data)
    assert restored.version == "v0.2"
    assert len(restored.records) == 1
    assert restored.records[0].sales == 500_000
