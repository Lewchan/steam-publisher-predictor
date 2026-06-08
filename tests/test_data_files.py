"""Tests for genre_pools.json and tag_mapping.json data files."""

from __future__ import annotations

from pathlib import Path

import pytest

from steam_publisher_predictor.services.user_pool import _load_json

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "steam_publisher_predictor" / "data"


def test_genre_pools_file_exists() -> None:
    filepath = DATA_DIR / "genre_pools.json"
    assert filepath.exists(), "genre_pools.json must exist for user_pool estimation"


def test_tag_mapping_file_exists() -> None:
    filepath = DATA_DIR / "tag_mapping.json"
    assert filepath.exists(), "tag_mapping.json must exist for tag-to-genre mapping"


def test_genre_pools_valid_structure() -> None:
    pools = _load_json("genre_pools.json")
    assert isinstance(pools, list)
    assert len(pools) > 0

    required_fields = {"genre_id", "genre_name", "base_pool"}
    for pool in pools:
        assert required_fields.issubset(pool.keys()), f"Missing fields in genre pool: {pool}"
        assert isinstance(pool["base_pool"], int), f"base_pool must be int: {pool['genre_id']}"
        assert pool["base_pool"] > 0, f"base_pool must be positive: {pool['genre_id']}"
        assert isinstance(pool["genre_id"], str), f"genre_id must be string: {pool}"
        assert isinstance(pool["genre_name"], str), f"genre_name must be string: {pool}"


def test_tag_mapping_valid_structure() -> None:
    mappings = _load_json("tag_mapping.json")
    assert isinstance(mappings, list)
    assert len(mappings) > 0

    required_fields = {"steam_tag", "genre_id", "weight"}
    for mapping in mappings:
        assert required_fields.issubset(mapping.keys()), f"Missing fields in tag mapping: {mapping}"
        assert isinstance(mapping["steam_tag"], str), f"steam_tag must be string: {mapping}"
        assert isinstance(mapping["genre_id"], str), f"genre_id must be string: {mapping}"
        assert isinstance(mapping["weight"], float), f"weight must be float: {mapping}"
        assert 0 < mapping["weight"] <= 1.0, f"weight must be between 0 and 1: {mapping}"


def test_genre_pool_ids_are_unique() -> None:
    pools = _load_json("genre_pools.json")
    ids = [p["genre_id"] for p in pools]
    assert len(ids) == len(set(ids)), "genre_id values must be unique"


def test_tag_mapping_covered_genres_exist_in_pool() -> None:
    pools = _load_json("genre_pools.json")
    pool_ids = {p["genre_id"] for p in pools}
    mappings = _load_json("tag_mapping.json")

    for mapping in mappings:
        assert mapping["genre_id"] in pool_ids, (
            f"Tag mapping references non-existent genre_id: {mapping['genre_id']}"
        )
