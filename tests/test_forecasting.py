from steam_publisher_predictor.models import ManualInputs, SteamGame
from steam_publisher_predictor.services.calculator import calculate_sales
from steam_publisher_predictor.services.quality import estimate_quality
from steam_publisher_predictor.services.user_pool import estimate_user_pool


def make_game() -> SteamGame:
    return SteamGame(
        app_id=42,
        name="Example Game",
        url="https://store.steampowered.com/app/42/",
        developer_names=["Studio"],
        publisher_names=["Publisher"],
        genres=["Action RPG", "Open World"],
        steam_tags=["Open World", "Survival", "Anime", "Crafting"],
        categories=["Single-player", "Steam Achievements"],
        supported_languages=["English", "Chinese", "Japanese"],
        price_usd=29.99,
        review_count=12345,
        review_score=8.7,
        metacritic_score=79,
        dlc_count=1,
        required_age=0,
        has_demo=False,
        has_achievements=True,
        is_free=False,
        coming_soon=False,
        release_date="2025-01-01",
        short_description="A compact test description.",
    )


def test_quality_score_stays_in_expected_range() -> None:
    quality = estimate_quality(make_game(), ManualInputs())

    assert 0 <= quality.quality_score <= 10
    assert quality.quality_confidence > 0.5
    assert quality.rating_strength > 6


def test_user_pool_maps_tags_into_weighted_buckets() -> None:
    pool = estimate_user_pool(make_game(), ManualInputs())

    assert pool.estimated_user_pool > 0
    assert pool.matches
    assert any(match.genre_id == "open_world_survival" for match in pool.matches)


def test_sales_calculation_caps_cl_at_three() -> None:
    manual_inputs = ManualInputs(
        art_base=10,
        gameplay_depth=10,
        scope=10,
        narrative=10,
        ip_factor=1.0,
        influencer_factor=1.0,
        exposure_base=0.5,
        intent_base=0.4,
        purchase_base=0.35,
        platform_fit=1.2,
        region_fit=1.1,
        price_fit=1.1,
        overlap_adjustment=0.95,
        discussion_manual_score=10,
        persistence_manual_score=10,
        analyst_adjustment=1.5,
        sexual_or_gore=True,
        extreme_novelty=True,
        real_time_juice=True,
        systemic_interlock=True,
        complex_system=True,
        linear_experience=True,
    )

    result = calculate_sales(make_game(), manual_inputs)

    assert 2.9 < result.cl_score <= 3.0
    assert result.sales > 0
