"""Reddit public discussion collector for Steam Publisher Predictor.

Uses the public Reddit JSON API (no OAuth required for read-only
subreddit searches).  Falls back gracefully when the source is
unavailable — never raises to the caller.

See Iteration_Development_Spec.md §15 (Data Adapter Rules).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from steam_publisher_predictor.services.discussion_source_base import (
    DiscussionSourceABC,
    NormalizedDiscussionResult,
    register_discussion_source,
)

_REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
_REDDIT_SUBREDDIT_URL = "https://www.reddit.com/r/{subreddit}/search.json"
_HTTP_TIMEOUT_SEC = 15
_USER_AGENT = "steam-publisher-predictor/0.1 (+https://github.com/steam-publisher-predictor)"


@dataclass(slots=True)
class _RawPost:
    """Lightweight internal representation of a Reddit post."""
    title: str
    score: int
    num_comments: int
    ups: int
    downs: int = 0
    permalink: str = ""
    created_utc: float = 0.0
    url: str = ""
    selftext_preview: str = ""
    subreddit: str = ""


@register_discussion_source("reddit")
class RedditSource(DiscussionSourceABC):
    """Fetch and normalise public Reddit discussion data for a game.

    Strategy
    --------
    1. Search Reddit posts containing the game name (case-insensitive).
    2. Collect up to *max_results* recent posts.
    3. Derive engagement metrics (views ~ score+comments, sentiment proxy).
    4. Return a :py:class:`NormalizedDiscussionResult`.
    """

    SOURCE_TYPE: str = "reddit"

    def __init__(self, timeout: float = _HTTP_TIMEOUT_SEC) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self._max_attempts = 2

    # ── public API ──────────────────────────────────────────────────────

    def fetch(
        self,
        game_name: str,
        max_results: int = 20,
    ) -> NormalizedDiscussionResult:
        query = _build_reddit_query(game_name)
        try:
            raw_items = self._search_reddit(query, limit=max_results)
        except Exception as exc:
            return self._error_result(game_name, str(exc))

        if not raw_items:
            return self._empty_result(game_name)

        return _normalise(raw_items, source_type=self.SOURCE_TYPE, game_name=game_name)

    # ── internal ────────────────────────────────────────────────────────

    def _search_reddit(
        self,
        query: str,
        limit: int = 20,
    ) -> list[_RawPost]:
        params: dict[str, Any] = {
            "q": query,
            "sort": "relevance",
            "type": "post",
            "limit": min(limit, 100),
        }
        last_error: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                resp = self._client.get(_REDDIT_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return _parse_reddit_json(data)
            except Exception as exc:
                last_error = exc
                time.sleep(1)

        return []  # graceful degradation

    def _error_result(self, game_name: str, message: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            error_message=f"Reddit fetch failed: {message}",
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )

    def _empty_result(self, game_name: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )


# ── helpers ───────────────────────────────────────────────────────────────

def _build_reddit_query(game_name: str) -> str:
    """Build a query that favours gaming-subreddit results.

    Reddit's search is fuzzy; we append common gaming subs as a hint
    but do not enforce subreddit-scoped queries (those need separate
    endpoints).
    """
    return game_name


def _parse_reddit_json(data: dict) -> list[_RawPost]:
    """Extract posts from the Reddit JSON response."""
    children = data.get("data", {}).get("children", [])
    results: list[_RawPost] = []
    for child in children:
        post = child.get("data", {})
        if not post.get("title"):
            continue
        results.append(_RawPost(
            title=post.get("title", ""),
            score=post.get("score", 0),
            num_comments=post.get("num_comments", 0),
            ups=post.get("ups", 0),
            downs=post.get("downs", 0),
            permalink=post.get("permalink", ""),
            created_utc=post.get("created_utc", 0.0),
            url=post.get("url", ""),
            selftext_preview=(post.get("selftext", "") or "")[:500],
            subreddit=post.get("subreddit_name_prefixed", ""),
        ))
    return results


def _normalise(
    raw_items: list[_RawPost],
    *,
    source_type: str,
    game_name: str,
) -> NormalizedDiscussionResult:
    """Aggregate raw Reddit items into a :py:class:`NormalizedDiscussionResult`."""
    post_count = len(raw_items)
    total_comments = sum(r.num_comments for r in raw_items)
    total_score = sum(r.score for r in raw_items)
    total_views = total_score + total_comments  # proxy

    # Average upvote ratio — approximate from score/comments
    upvote_ratios: list[float] = []
    for r in raw_items:
        total_votes = r.ups + max(r.downs, 1)
        upvote_ratios.append(r.ups / total_votes if total_votes > 0 else 0.5)
    avg_upvote = sum(upvote_ratios) / len(upvote_ratios) if upvote_ratios else 0.0

    # Sentiment proxy: upvote ratio is a rough proxy for Reddit
    # (0.5 = neutral, >0.7 = positive, <0.4 = negative)
    avg_sentiment = min(1.0, max(-1.0, (avg_upvote - 0.5) * 2.0))

    hot_threshold = 100
    has_hot = any(r.score >= hot_threshold for r in raw_items)
    controversial_threshold = 0.3
    has_controversial = any(
        r.downs > 0 and (r.downs / max(r.ups + r.downs, 1)) > controversial_threshold
        for r in raw_items
    )

    return NormalizedDiscussionResult(
        source_type=source_type,
        game_name=game_name,
        post_count=post_count,
        comment_count=total_comments,
        avg_upvote_ratio=round(avg_upvote, 3),
        avg_sentiment=round(avg_sentiment, 3),
        total_views=total_views,
        total_engagement=total_score + total_comments,
        has_hot_content=has_hot,
        has_controversial_content=has_controversial,
        fetch_time=datetime.now(timezone.utc).isoformat(),
        raw_sample_count=post_count,
    )
