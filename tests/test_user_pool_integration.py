"""Integration tests for user_pool estimation with the data files."""

from __future__ import annotations

from steam_publisher_predictor.models import ManualInputs, SteamGame, SteamDbStats
from steam_publisher_predictor.services.user_pool import estimate_user_pool


def _make_balatro_like_game() -> SteamGame:
    """Create a game similar to Balatro (roguelike card game)."""
    return SteamGame(
        app_id=2379780,
        name="Balatro",
        url="https://store.steampowered.com/app/2379780/",
        developer_names=["Playstack"],
        publisher_names=["Archibite Studios"],
        genres=["Indie", "Card Game"],
        steam_tags=["Roguelike", "Card Game", "Roguelite", "Deckbuilding", "Indie", "Strategy"],
        categories=["Single-player"],
        supported_languages=["English", "French", "German", "Spanish", "Japanese"],
        price_usd=14.99,
        review_count=100000,
        review_score=9.7,
        metacritic_score=85,
        dlc_count=0,
        required_age=0,
        has_demo=False,
        has_achievements=True,
        is_free=False,
        coming_soon=False,
        release_date="2024-02-20",
        short_description="A poker-themed roguelike deckbuilder.",
    )


def _make_survival_crafting_game() -> SteamGame:
    """Create a game similar to Palworld (survival crafting)."""
    return SteamGame(
        app_id=1623730,
        name="Palworld",
        url="https://store.steampowered.com/app/1623730/",
        developer_names=["Pocketpair"],
        publisher_names=["Pocketpair"],
        genres=["Action", "Adventure", "Indie"],
        steam_tags=["Survival", "Crafting", "Open World", "Monster Hunter", "Multiplayer", "Open World Survival Craft"],
        categories=["Single-player", "Multi-player", "Online Co-Op"],
        supported_languages=["English", "Japanese", "Korean", "Chinese"],
        price_usd=29.99,
        review_count=200000,
        review_score=8.5,
        metacritic_score=75,
        dlc_count=0,
        required_age=0,
        has_demo=True,
        has_achievements=True,
        is_free=False,
        coming_soon=False,
        release_date="2024-01-19",
        short_description="Fight, farm, build, and work alongside mysterious creatures called Pals.",
    )


def _make_farm_sim_game() -> SteamGame:
    """Create a game similar to Stardew Valley (farming sim)."""
    return SteamGame(
        app_id=413150,
        name="Stardew Valley",
        url="https://store.steampowered.com/app/413150/",
        developer_names=["ConcernedApe"],
        publisher_names=["ConcernedApe"],
        genres=["Simulation", "RPG", "Indie"],
        steam_tags=["Farming Sim", "Life Sim", "Pixel Graphics", "Relaxing", "Co-op", "Cute"],
        categories=["Single-player"],
        supported_languages=["English", "French", "German", "Spanish", "Japanese", "Korean", "Chinese"],
        price_usd=14.99,
        review_count=500000,
        review_score=9.8,
        metacritic_score=87,
        dlc_count=0,
        required_age=0,
        has_demo=False,
        has_achievements=True,
        is_free=False,
        coming_soon=False,
        release_date="2016-02-26",
        short_description="You inherited the old farm plot of your grandfather in Stardew Valley.",
    )


def test_balatro_maps_to_roguelike_card() -> None:
    game = _make_balatro_like_game()
    pool = estimate_user_pool(game, ManualInputs())

    assert pool.estimated_user_pool > 0
    assert pool.matches
    # Should map to roguelite_card or roguelite_action
    genre_ids = {m.genre_id for m in pool.matches}
    assert any(g in genre_ids for g in {"roguelite_card", "roguelite_action"})


def test_survival_game_maps_to_survival_crafting() -> None:
    game = _make_survival_crafting_game()
    pool = estimate_user_pool(game, ManualInputs())

    assert pool.estimated_user_pool > 0
    assert pool.matches
    genre_ids = {m.genre_id for m in pool.matches}
    assert "survival_crafting" in genre_ids


def test_farm_sim_maps_to_farm_life_sim() -> None:
    game = _make_farm_sim_game()
    pool = estimate_user_pool(game, ManualInputs())

    assert pool.estimated_user_pool > 0
    assert pool.matches
    genre_ids = {m.genre_id for m in pool.matches}
    assert "farm_life_sim" in genre_ids


def test_user_pool_respects_override() -> None:
    game = _make_balatro_like_game()
    manual = ManualInputs(user_pool_override=5000000)
    pool = estimate_user_pool(game, manual)

    assert pool.estimated_user_pool == 5000000


def test_user_pool_with_no_tag_matches_falls_back() -> None:
    """Game with no matching tags should fall back to first genre pool."""
    game = SteamGame(
        app_id=999,
        name="Unknown Genre Game",
        url="https://store.steampowered.com/app/999/",
        genres=["Obscure Genre"],
        steam_tags=[],
        categories=[],
        supported_languages=[],
        price_usd=9.99,
        review_count=100,
        review_score=5.0,
        metacritic_score=0,
        dlc_count=0,
        required_age=0,
        has_demo=False,
        has_achievements=False,
        is_free=False,
        coming_soon=False,
        release_date="2025-01-01",
        short_description="A test game.",
    )
    pool = estimate_user_pool(game, ManualInputs())

    assert pool.estimated_user_pool > 0
    assert pool.matches


def test_user_pool_with_multipliers() -> None:
    """Overlapping tags should produce weighted pools with correct multipliers."""
    game = _make_survival_crafting_game()
    manual = ManualInputs(overlap_adjustment=0.8, platform_fit=1.0, region_fit=1.0, price_fit=1.0)
    pool = estimate_user_pool(game, manual)

    # weighted_genre_sum * overlap_adjustment * platform_fit * region_fit * price_fit = estimated
    expected = pool.weighted_genre_sum * manual.overlap_adjustment * manual.platform_fit * manual.region_fit * manual.price_fit
    assert pool.estimated_user_pool == int(expected)
