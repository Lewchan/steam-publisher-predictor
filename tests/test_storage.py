"""Tests for prediction record storage (save, load, list, delete)."""

from __future__ import annotations

from pathlib import Path

import pytest

from steam_publisher_predictor.models import ManualInputs, SteamGame
from steam_publisher_predictor.services.calculator import calculate_sales
from steam_publisher_predictor.services.storage import record as storage

DATA_DIR = Path(__file__).resolve().parent.parent / "test_data"


@pytest.fixture
def sample_game():
    return SteamGame(
        app_id=2379780,
        name="Balatro",
        url="https://store.steampowered.com/app/2379780/",
        genres=["Strategy", "Indie"],
        steam_tags=["Roguelike", "Card Game"],
        categories=["Single-player", "Steam Achievements"],
        supported_languages=["English"],
        price_usd=14.99,
        review_count=100000,
        review_score=9.7,
        metacritic_score=85,
        release_date="2024-02-20",
        short_description="A poker-themed roguelike deckbuilder.",
    )


@pytest.fixture
def sample_manual_inputs():
    return ManualInputs(
        art_base=7,
        gameplay_depth=8,
        scope=6,
        narrative=2,
        ip_factor=0.1,
        influencer_factor=0.6,
        user_pool_override=0,
        exposure_base=0.3,
        intent_base=0.25,
        purchase_base=0.3,
        peak_dau=5000,
        median_line=0.15,
        extreme_novelty=True,
        real_time_juice=True,
    )


@pytest.fixture(autouse=True)
def clean_data_dir():
    """Clean test data before and after each test."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("prediction_*.json"):
        f.unlink()
    yield
    for f in DATA_DIR.glob("prediction_*.json"):
        f.unlink()
    DATA_DIR.rmdir()


def test_save_and_load_record(sample_game, sample_manual_inputs):
    breakdown = calculate_sales(sample_game, sample_manual_inputs)
    path = storage.save_prediction_record(breakdown, "Balatro", data_dir=DATA_DIR)
    assert path.exists()

    loaded = storage.load_record("Balatro_record_placeholder", data_dir=DATA_DIR)
    # The record is stored under a UUID, so find it by scanning
    records = storage.list_records(data_dir=DATA_DIR)
    assert len(records) == 1
    assert records[0]["query"] == "Balatro"


def test_list_records_empty():
    records = storage.list_records(data_dir=DATA_DIR)
    assert records == []


def test_delete_record(sample_game, sample_manual_inputs):
    breakdown = calculate_sales(sample_game, sample_manual_inputs)
    storage.save_prediction_record(breakdown, "Balatro", data_dir=DATA_DIR)

    records = storage.list_records(data_dir=DATA_DIR)
    assert len(records) == 1
    record_id = records[0]["record_id"]

    assert storage.delete_record(record_id, data_dir=DATA_DIR) is True
    assert storage.load_record(record_id, data_dir=DATA_DIR) is None


def test_load_missing_record():
    assert storage.load_record("nonexistent_id", data_dir=DATA_DIR) is None


def test_delete_missing_record():
    assert storage.delete_record("nonexistent_id", data_dir=DATA_DIR) is False
