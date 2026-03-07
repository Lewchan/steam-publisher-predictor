from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SteamDbStats:
    url: str
    current_players: int = 0
    peak_24h: int = 0
    all_time_peak: int = 0
    followers: int = 0
    reviews: int = 0
    steamdb_rating: float = 0.0
    positive_reviews: int = 0
    negative_reviews: int = 0
    daily_active_users_rank: int = 0
    top_sellers_rank: int = 0
    wishlist_activity_rank: int = 0
    last_30_days_peak: int = 0
    has_data: bool = False
    unavailable_reason: str = ""


@dataclass(slots=True)
class SteamGame:
    app_id: int
    name: str
    url: str
    developer_names: list[str] = field(default_factory=list)
    publisher_names: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    steam_tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    supported_languages: list[str] = field(default_factory=list)
    price_usd: float = 0.0
    review_count: int = 0
    review_score: float = 0.0
    metacritic_score: int = 0
    dlc_count: int = 0
    required_age: int = 0
    has_demo: bool = False
    has_achievements: bool = False
    is_free: bool = False
    coming_soon: bool = False
    release_date: str | None = None
    short_description: str = ""
    steamdb: SteamDbStats | None = None


@dataclass(slots=True)
class ManualInputs:
    art_base: float = 5.0
    gameplay_depth: float = 5.0
    scope: float = 5.0
    narrative: float = 5.0
    ip_factor: float = 0.2
    influencer_factor: float = 0.2
    exposure_base: float = 0.2
    intent_base: float = 0.25
    purchase_base: float = 0.3
    platform_fit: float = 1.0
    region_fit: float = 1.0
    price_fit: float = 1.0
    overlap_adjustment: float = 0.75
    user_pool_override: int = 0
    discussion_manual_score: float = 5.0
    persistence_manual_score: float = 5.0
    analyst_adjustment: float = 0.0
    peak_dau: int = 0
    median_line: float = 0.0
    sexual_or_gore: bool = False
    extreme_novelty: bool = False
    real_time_juice: bool = False
    systemic_interlock: bool = False
    complex_system: bool = False
    linear_experience: bool = False


@dataclass(slots=True)
class QualityBreakdown:
    rating_strength: float
    rating_confidence: float
    proof_strength: float
    discussion_count_signal: float
    discussion_engagement_signal: float
    discussion_sentiment_signal: float
    discussion_strength: float
    persistence_strength: float
    analyst_adjustment: float
    quality_score: float
    quality_confidence: float
    missing_quality_sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UserPoolMatch:
    genre_id: str
    genre_name: str
    source_label: str
    mapping_weight: float
    base_pool: int
    weighted_pool: float


@dataclass(slots=True)
class UserPoolBreakdown:
    matches: list[UserPoolMatch]
    weighted_genre_sum: float
    overlap_adjustment: float
    platform_fit: float
    region_fit: float
    price_fit: float
    estimated_user_pool: int


@dataclass(slots=True)
class SalesBreakdown:
    game: SteamGame
    quality: QualityBreakdown
    user_pool: UserPoolBreakdown
    manual_inputs: ManualInputs
    cl_base_raw: float
    cl_base: float
    amplification_tag_total: float
    showmanship_raw: float
    showmanship_effect: float
    brand_factor: float
    cl_raw: float
    cl_score: float
    base_conversion: float
    sales: float
    annual_long_tail_sales: float | None
