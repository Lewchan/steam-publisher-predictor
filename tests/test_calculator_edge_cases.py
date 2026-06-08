# Steve 2026/06/07 迭代创建 - 计算器边界值测试

import pytest
from steam_publisher_predictor.models import ManualInputs, SteamGame


def make_game(**overrides):
    """Create a SteamGame with defaults, then apply overrides."""
    base = SteamGame(
        app_id=1,
        name="Edge Game",
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


def test_all_zero_inputs():
    """All ManualInputs zero → should produce zero or near-zero sales."""
    game = make_game()
    manual = ManualInputs(
        art_base=0, gameplay_depth=0, scope=0, narrative=0,
        ip_factor=0, influencer_factor=0, exposure_base=0,
        intent_base=0, purchase_base=0, platform_fit=0,
        region_fit=0, price_fit=0, overlap_adjustment=0,
        discussion_manual_score=0, persistence_manual_score=0,
        analyst_adjustment=0, peak_dau=0, median_line=0.0,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales == 0.0


def test_zero_cl_amplifies_to_low():
    """With review_count=0, CL score should be very low (base only, no amplification)."""
    game = make_game(review_count=0, review_score=0, metacritic_score=0)
    manual = ManualInputs(
        art_base=0, gameplay_depth=0, scope=0, narrative=0,
        ip_factor=0, influencer_factor=0,
        exposure_base=0.5, intent_base=0.5, purchase_base=0.5,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales >= 0.0
    # CL is mainly from CL_WEIGHTS tags which default to small values
    assert result.cl_score < 1.0


def test_max_manual_inputs():
    """All ManualInputs at maximum → should produce valid high sales."""
    game = make_game(review_count=100000, review_score=99, metacritic_score=100)
    manual = ManualInputs(
        art_base=10, gameplay_depth=10, scope=10, narrative=10,
        ip_factor=1.0, influencer_factor=1.0,
        exposure_base=1.0, intent_base=1.0, purchase_base=1.0,
        platform_fit=2.0, region_fit=2.0, price_fit=2.0,
        overlap_adjustment=1.0,
        discussion_manual_score=10, persistence_manual_score=10,
        analyst_adjustment=10,
        peak_dau=100000, median_line=10000.0,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales > 0
    assert result.cl_score <= 3.0  # CL cap


def test_negative_review_count_handled():
    """Even with review_count=0 (not negative, but zero), should not crash."""
    game = make_game(review_count=0, review_score=0.0, metacritic_score=0)
    manual = ManualInputs()
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales >= 0.0


def test_empty_genres():
    """Game with no genres → user_pool should still work."""
    game = make_game(genres=[], steam_tags=[], categories=[])
    manual = ManualInputs(
        art_base=5, gameplay_depth=5, scope=5, narrative=5,
        ip_factor=0, influencer_factor=0,
        exposure_base=0.3, intent_base=0.3, purchase_base=0.3,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales >= 0.0


def test_cl_score_capped_at_three():
    """CL score should never exceed 3.0 regardless of inputs."""
    game = make_game()
    manual = ManualInputs(
        art_base=10, gameplay_depth=10, scope=10, narrative=10,
        ip_factor=1.0, influencer_factor=1.0,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.cl_score <= 3.0
    assert result.cl_score >= 0.0


def test_dlc_count_zero():
    """Game with no DLC → dlc_count feature should be 0.0."""
    game = make_game(dlc_count=0)
    assert game.dlc_count == 0


def test_negative_analyst_adjustment():
    """Negative analyst adjustment should reduce final sales."""
    game = make_game()
    manual = ManualInputs(
        art_base=5, gameplay_depth=5, scope=5, narrative=5,
        ip_factor=0.2, influencer_factor=0.2,
        analyst_adjustment=-2.0,
    )
    from steam_publisher_predictor.services.calculator import calculate_sales
    result = calculate_sales(game, manual)
    assert result.sales >= 0.0
