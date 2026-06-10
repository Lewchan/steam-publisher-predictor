"""Service layer for Steam Publisher Predictor."""

from steam_publisher_predictor.services import benchmark, discussion_source_base, steamdb_http

# Import discussion source modules to trigger @register_discussion_source decorators
from steam_publisher_predictor.services import reddit_discussion, youtube_discussion  # noqa: F401

from steam_publisher_predictor.services.discussion_source_base import (
    DiscussionSourceABC,
    NormalizedDiscussionResult,
)

__all__ = [
    "benchmark",
    "discussion_source_base",
    "NormalizedDiscussionResult",
    "DiscussionSourceABC",
    "steamdb_http",
    "reddit_discussion",
    "youtube_discussion",
]
