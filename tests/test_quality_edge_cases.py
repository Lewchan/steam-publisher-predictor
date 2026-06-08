# Steve 2026/06/07 迭代创建 - 质量评分边界测试

import pytest
from steam_publisher_predictor.models import ManualInputs, SteamDbStats, SteamGame


def make_game(**overrides):
    base = SteamGame(
        app_id=1,
        name="Quality Edge Game",
        url="https://store.steampowered.com/app/1/",
        developer_names=["Dev"],
        publisher_names=["Pub"],
        genres=["Action"],
        steam_tags=["Action"],
        categories=["Single-player"],
        supported_languages=["English"],
        price_usd=9.99,
        review_count=100,
        review_score=70.0,
        metacritic_score=60,
        dlc_count=0,
        required_age=0,
        has_demo=False,
        has_achievements=False,
        is_free=False,
        coming_soon=False,
        release_date="2024-01-01",
        short_description="Edge test.",
        steamdb=None,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_zero_reviews_quality_score():
    """Zero reviews → quality_score should still be valid (not NaN/Inf)."""
    game = make_game(review_count=0, review_score=0.0, metacritic_score=0)
    manual = ManualInputs()
    from steam_publisher_predictor.services.quality import estimate_quality
    result = estimate_quality(game, manual)
    assert result.quality_score >= 0.0
    assert result.quality_score <= 10.0
    assert result.quality_confidence >= 0.0


def test_no_steamdb_data():
    """Game with no SteamDB data → quality should use fallback."""
    game = make_game(steamdb=None)
    manual = ManualInputs()
    from steam_publisher_predictor.services.quality import estimate_quality
    result = estimate_quality(game, manual)
    assert result.quality_score >= 0.0
    assert result.quality_score <= 10.0


def test_full_steamdb_data_boosts_quality():
    """Full SteamDB data should increase quality_score vs no data."""
    game_with_steamdb = make_game(
        review_count=50000, review_score=90.0, metacritic_score=90,
        steamdb=SteamDbStats(
            url="https://steamdb.info/app/1/",
            current_players=5000, peak_24h=8000, all_time_peak=20000,
            followers=100000, reviews=50000,
            steamdb_rating=95.0, positive_reviews=47000, negative_reviews=3000,
            daily_active_users_rank=200, top_sellers_rank=300,
            wishlist_activity_rank=250, last_30_days_peak=7000, has_data=True,
        ),
    )
    game_no_steamdb = make_game(
        review_count=50000, review_score=90.0, metacritic_score=90,
        steamdb=None,
    )
    manual = ManualInputs()

    from steam_publisher_predictor.services.quality import estimate_quality
    result_with = estimate_quality(game_with_steamdb, manual)
    result_without = estimate_quality(game_no_steamdb, manual)

    # SteamDB data should contribute positively
    assert result_with.quality_score >= result_without.quality_score


def test_all_missing_quality_sources():
    """All quality sources missing → confidence should be low."""
    game = make_game(review_count=0, review_score=0.0, metacritic_score=0, steamdb=None)
    manual = ManualInputs(
        discussion_manual_score=0, persistence_manual_score=0,
    )
    from steam_publisher_predictor.services.quality import estimate_quality
    result = estimate_quality(game, manual)
    assert len(result.missing_quality_sources) > 0
    assert result.quality_confidence < 0.5  # Should be low confidence


def test_high_quality_confidence_with_full_data():
    """All sources present → confidence should be high."""
    game = make_game(
        review_count=100000, review_score=95.0, metacritic_score=95,
        steamdb=SteamDbStats(
            url="https://steamdb.info/app/1/",
            current_players=10000, peak_24h=15000, all_time_peak=50000,
            followers=500000, reviews=100000,
            steamdb_rating=98.0, positive_reviews=97000, negative_reviews=3000,
            daily_active_users_rank=50, top_sellers_rank=80,
            wishlist_activity_rank=60, last_30_days_peak=12000, has_data=True,
        ),
    )
    manual = ManualInputs(
        discussion_manual_score=8, persistence_manual_score=8,
    )
    from steam_publisher_predictor.services.quality import estimate_quality
    result = estimate_quality(game, manual)
    assert result.quality_score > 0
    assert result.quality_confidence > 0.3  # Should be moderate-high


def test_quality_score_within_range():
    """Quality score must always be in [0, 10]."""
    for review_count in [0, 100, 10000, 500000]:
        game = make_game(review_count=review_count, review_score=70.0, metacritic_score=50)
        manual = ManualInputs()
        from steam_publisher_predictor.services.quality import estimate_quality
        result = estimate_quality(game, manual)
        assert 0 <= result.quality_score <= 10, f"review_count={review_count}: score={result.quality_score}"


def test_analyst_adjustment_positive():
    """Positive analyst adjustment should increase quality."""
    game = make_game()
    manual_base = ManualInputs(
        discussion_manual_score=5, persistence_manual_score=5,
    )
    manual_adj = ManualInputs(
        discussion_manual_score=5, persistence_manual_score=5,
        analyst_adjustment=2.0,
    )
    from steam_publisher_predictor.services.quality import estimate_quality
    result_base = estimate_quality(game, manual_base)
    result_adj = estimate_quality(game, manual_adj)
    assert result_adj.quality_score >= result_base.quality_score
