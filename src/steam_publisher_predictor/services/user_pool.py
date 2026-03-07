from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from steam_publisher_predictor.models import ManualInputs, SteamGame, UserPoolBreakdown, UserPoolMatch

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PRIMARY_GENRE_MULTIPLIER = 1.0
SECONDARY_GENRE_MULTIPLIER = 0.6
TERTIARY_GENRE_MULTIPLIER = 0.35


def estimate_user_pool(game: SteamGame, manual_inputs: ManualInputs) -> UserPoolBreakdown:
    genre_table = _load_json("genre_pools.json")
    mapping_table = _load_json("tag_mapping.json")

    genres_by_id = {item["genre_id"]: item for item in genre_table}
    raw_scores: dict[str, float] = defaultdict(float)
    best_source_label: dict[str, str] = {}

    source_labels = [*game.genres, *game.steam_tags, *game.categories]
    lowered_sources = {label.lower(): label for label in source_labels}

    for mapping in mapping_table:
        tag = str(mapping["steam_tag"]).lower()
        genre_id = str(mapping["genre_id"])
        weight = float(mapping["weight"])
        for lowered, original in lowered_sources.items():
            if tag == lowered or tag in lowered:
                raw_scores[genre_id] += weight
                best_source_label.setdefault(genre_id, original)

    if not raw_scores and game.genres:
        fallback = next(iter(genres_by_id.values()))
        raw_scores[str(fallback["genre_id"])] = 0.5
        best_source_label[str(fallback["genre_id"])] = game.genres[0]

    ordered_matches = sorted(
        raw_scores.items(),
        key=lambda item: (item[1] * genres_by_id.get(item[0], {}).get("base_pool", 0)),
        reverse=True,
    )[:3]

    multipliers = [
        PRIMARY_GENRE_MULTIPLIER,
        SECONDARY_GENRE_MULTIPLIER,
        TERTIARY_GENRE_MULTIPLIER,
    ]

    matches: list[UserPoolMatch] = []
    weighted_genre_sum = 0.0
    for index, (genre_id, mapping_weight) in enumerate(ordered_matches):
        genre = genres_by_id[genre_id]
        base_pool = int(genre["base_pool"])
        weighted_pool = base_pool * mapping_weight * multipliers[index]
        weighted_genre_sum += weighted_pool
        matches.append(
            UserPoolMatch(
                genre_id=genre_id,
                genre_name=str(genre["genre_name"]),
                source_label=best_source_label.get(genre_id, genre_id),
                mapping_weight=mapping_weight,
                base_pool=base_pool,
                weighted_pool=weighted_pool,
            )
        )

    adjusted_pool = weighted_genre_sum * manual_inputs.overlap_adjustment
    adjusted_pool *= manual_inputs.platform_fit
    adjusted_pool *= manual_inputs.region_fit
    adjusted_pool *= manual_inputs.price_fit

    if manual_inputs.user_pool_override > 0:
        estimated_user_pool = int(manual_inputs.user_pool_override)
    else:
        estimated_user_pool = int(max(0.0, adjusted_pool))

    return UserPoolBreakdown(
        matches=matches,
        weighted_genre_sum=weighted_genre_sum,
        overlap_adjustment=manual_inputs.overlap_adjustment,
        platform_fit=manual_inputs.platform_fit,
        region_fit=manual_inputs.region_fit,
        price_fit=manual_inputs.price_fit,
        estimated_user_pool=estimated_user_pool,
    )


def _load_json(filename: str) -> list[dict[str, object]]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
