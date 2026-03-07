from __future__ import annotations

import math
from datetime import date

from steam_publisher_predictor.models import ManualInputs, QualityBreakdown, SteamGame

GENRE_BASELINE = 6.2


def estimate_quality(game: SteamGame, manual_inputs: ManualInputs) -> QualityBreakdown:
    review_count = max(game.review_count, 0)
    normalized_rating = _normalize_rating(game.review_score)
    rating_confidence = min(1.0, math.log1p(review_count) / math.log1p(50000))
    rating_strength = normalized_rating * rating_confidence + GENRE_BASELINE * (1 - rating_confidence)

    proof_strength = min(10.0, math.log10(review_count + 1) * 2.0)
    discussion_count_signal = min(10.0, math.log10(review_count + 1) * 1.8 + min(len(game.steam_tags) * 0.15, 1.5))
    discussion_engagement_signal = min(
        10.0,
        3.0
        + min(game.metacritic_score / 100 * 2.0, 2.0)
        + min(len(game.supported_languages) * 0.12, 1.8),
    )
    discussion_sentiment_signal = min(
        10.0,
        max(0.0, normalized_rating * 0.75 + (manual_inputs.discussion_manual_score * 0.25)),
    )
    discussion_strength = min(
        10.0,
        discussion_count_signal * 0.4
        + discussion_engagement_signal * 0.25
        + discussion_sentiment_signal * 0.35,
    )
    persistence_strength = _estimate_persistence(game, manual_inputs.persistence_manual_score)

    quality_score = min(
        10.0,
        max(
            0.0,
            rating_strength * 0.45
            + proof_strength * 0.20
            + discussion_strength * 0.20
            + persistence_strength * 0.15
            + manual_inputs.analyst_adjustment,
        ),
    )

    missing_sources: list[str] = []
    if review_count == 0:
        missing_sources.append("steam_reviews")
    if not game.steam_tags:
        missing_sources.append("steam_tags")
    if game.metacritic_score == 0:
        missing_sources.append("metacritic")

    confidence_penalty = 0.0
    if "steam_reviews" in missing_sources:
        confidence_penalty += 0.3
    if "steam_tags" in missing_sources:
        confidence_penalty += 0.1
    if "metacritic" in missing_sources:
        confidence_penalty += 0.05
    quality_confidence = max(0.0, min(1.0, rating_confidence + 0.25 - confidence_penalty))

    return QualityBreakdown(
        rating_strength=rating_strength,
        rating_confidence=rating_confidence,
        proof_strength=proof_strength,
        discussion_count_signal=discussion_count_signal,
        discussion_engagement_signal=discussion_engagement_signal,
        discussion_sentiment_signal=discussion_sentiment_signal,
        discussion_strength=discussion_strength,
        persistence_strength=persistence_strength,
        analyst_adjustment=manual_inputs.analyst_adjustment,
        quality_score=quality_score,
        quality_confidence=quality_confidence,
        missing_quality_sources=missing_sources,
    )


def _normalize_rating(review_score: float) -> float:
    if review_score <= 0:
        return GENRE_BASELINE
    if review_score > 10:
        return min(10.0, review_score / 10.0)
    return min(10.0, review_score)


def _estimate_persistence(game: SteamGame, manual_score: float) -> float:
    if game.release_date:
        days_since_release = max((date.today() - date.fromisoformat(game.release_date)).days, 1)
    else:
        days_since_release = 30

    reviews_per_month = game.review_count / max(days_since_release / 30.0, 1.0)
    objective_signal = min(10.0, math.log10(reviews_per_month + 1) * 3.0 + 2.0)
    return min(10.0, max(0.0, objective_signal * 0.6 + manual_score * 0.4))
