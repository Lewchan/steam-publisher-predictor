# Webber 2026/06/11 新增: Bilibili 公开讨论数据采集器
"""Bilibili public discussion collector for Steam Publisher Predictor.

Uses the public Bilibili search API (SAPI) to fetch video results
for a given game name. Falls back gracefully when the source is
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

_BILIBILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"
_BILIBILI_VIDEO_INFO_URL = "https://api.bilibili.com/x/web-interface/view"
_HTTP_TIMEOUT_SEC = 15
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class _VideoItem:
    """Lightweight internal representation of a Bilibili video."""
    title: str = ""
    bvid: str = ""
    aid: int = 0
    view_count: int = 0
    danmaku_count: int = 0
    comment_count: int = 0
    like_count: int = 0
    coin_count: int = 0
    favorite_count: int = 0
    share_count: int = 0
    pubdate: str = ""
    owner_name: str = ""
    owner_mid: int = 0
    url: str = ""
    duration_seconds: int = 0
    description: str = ""
    ctime: int = 0
    pubtime: int = 0


@register_discussion_source("bilibili")
class BilibiliSource(DiscussionSourceABC):
    """Fetch and normalise public Bilibili discussion data for a game.

    Strategy
    --------
    1. Search Bilibili via the public SAPI search endpoint (no auth required).
    2. Collect up to *max_results* recent videos matching the game name.
    3. Derive engagement metrics (views, likes, comments, danmaku, coins, favorites).
    4. Return a :py:class:`NormalizedDiscussionResult`.
    """

    SOURCE_TYPE: str = "bilibili"

    def __init__(self, timeout: float = _HTTP_TIMEOUT_SEC) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://www.bilibili.com/",
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
        try:
            raw_items = self._search_bilibili(game_name, limit=max_results)
        except Exception as exc:
            return self._error_result(game_name, str(exc))

        if not raw_items:
            return self._empty_result(game_name)

        return _normalise(raw_items, source_type=self.SOURCE_TYPE, game_name=game_name)

    # ── internal ────────────────────────────────────────────────────────

    def _search_bilibili(
        self,
        game_name: str,
        limit: int = 20,
    ) -> list[_VideoItem]:
        """Search Bilibili via public SAPI.

        Bilibili SAPI (search/all/v2) returns results across multiple
        result types (video, user, article, etc.). We filter for video
        results only.
        """
        params: dict[str, Any] = {
            "keyword": game_name,
            "order": "totalrank",  # Sort by total rank (views + engagement)
            "page": 1,
            "page_size": min(limit, 50),
        }
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                resp = self._client.get(_BILIBILI_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return _parse_bilibili_search(data, limit)
            except Exception as exc:
                last_error = exc
                if attempt < self._max_attempts - 1:
                    time.sleep(1)
        if last_error is not None:
            raise last_error
        return []

    def _error_result(self, game_name: str, message: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            error_message=f"Bilibili fetch failed: {message}",
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )

    def _empty_result(self, game_name: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )


# ── helpers ───────────────────────────────────────────────────────────────

def _parse_bilibili_search(data: dict, limit: int = 20) -> list[_VideoItem]:
    """Extract video results from Bilibili search API response.

    The SAPI search/all/v2 endpoint returns results grouped by type
    in the `data.result` section. We look for `video` type results.
    """
    result_section = data.get("data", {}).get("result", {})
    video_results = result_section.get("video", {})
    datas = video_results.get("numResults", 0)
    if datas == 0:
        # Try old API format (data is directly in result)
        r = data.get("data", {})
        if isinstance(r, dict) and "video" in r:
            video_results = r["video"]
            datas = video_results.get("numResults", 0)

    if datas == 0:
        return []

    results: list[_VideoItem] = []
    for item in video_results.get("numResultsData", []) or video_results.get("result", []):
        vid = _extract_video(item)
        if vid and vid.title:
            results.append(vid)
            if len(results) >= limit:
                break

    return results


def _extract_video(data: dict) -> _VideoItem | None:
    """Extract a single video record from Bilibili search result."""
    if not data:
        return None

    bvid = data.get("bvid", "")
    aid = data.get("aid", 0)
    if not bvid and not aid:
        return None

    pubdate = data.get("pubdate", 0)
    if pubdate:
        try:
            pubdate = datetime.fromtimestamp(pubdate, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError, TypeError):
            pubdate = ""

    return _VideoItem(
        title=data.get("title", ""),
        bvid=bvid,
        aid=aid,
        view_count=data.get("view", 0),
        danmaku_count=data.get("danmaku", 0),
        comment_count=data.get("reply", 0),
        like_count=data.get("like", 0),
        coin_count=data.get("coins", 0),
        favorite_count=data.get("favorites", 0),
        share_count=data.get("share", 0),
        pubdate=pubdate,
        owner_name=data.get("author", ""),
        owner_mid=data.get("mid", 0),
        url=f"https://www.bilibili.com/video/{bvid}" if bvid else "",
        duration_seconds=_parse_duration(data.get("duration", 0)),
        description=data.get("description", ""),
        ctime=data.get("ctime", 0),
        pubtime=data.get("pubtime", 0),
    )


def _parse_duration(raw) -> int:
    """Parse Bilibili duration field to seconds.

    Bilibili may return duration as:
    - integer: seconds
    - string "MM:SS" or "HH:MM:SS"
    - float: seconds
    """
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        parts = raw.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                return 0
        elif len(parts) == 3:
            try:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                return 0
    return 0


# ── Normalisation ───────────────────────────────────────────────────────────

def _normalise(
    raw_items: list[_VideoItem],
    *,
    source_type: str,
    game_name: str,
) -> NormalizedDiscussionResult:
    """Aggregate raw Bilibili items into a :py:class:`NormalizedDiscussionResult`."""
    video_count = len(raw_items)

    total_views = sum(r.view_count for r in raw_items)
    total_likes = sum(r.like_count for r in raw_items)
    total_comments = sum(r.comment_count for r in raw_items)
    total_danmaku = sum(r.danmaku_count for r in raw_items)
    total_coins = sum(r.coin_count for r in raw_items)
    total_favorites = sum(r.favorite_count for r in raw_items)
    total_shares = sum(r.share_count for r in raw_items)

    # Engagement = views + comments + danmaku + likes + coins + favorites + shares
    total_engagement = (
        total_views + total_likes + total_comments
        + total_danmaku + total_coins + total_favorites + total_shares
    )

    # Upvote ratio proxy: likes / (likes + comments)
    like_ratio = total_likes / max(total_likes + total_comments, 1)
    # Danmaku ratio as secondary signal (indicates real-time engagement)
    danmaku_ratio = total_danmaku / max(total_views, 1)

    # Sentiment proxy: weighted combination
    # Higher likes/comments ratio = more positive
    # Higher danmaku ratio = more active/enthusiastic
    if total_likes + total_comments > 0:
        sentiment = (
            like_ratio * 0.6
            + min(danmaku_ratio * 100, 1.0) * 0.4  # Normalize danmaku ratio
        )
        sentiment = min(1.0, max(-1.0, (sentiment - 0.5) * 2.0))
    else:
        sentiment = 0.0

    # Hot content: any video with > 1000 views
    has_hot = any(r.view_count >= 1000 for r in raw_items)

    # Controversial: high comment-to-like ratio
    has_controversial = any(
        r.like_count > 0 and (r.comment_count / max(r.like_count, 1)) > 3.0
        for r in raw_items
    )

    return NormalizedDiscussionResult(
        source_type=source_type,
        game_name=game_name,
        post_count=video_count,
        comment_count=total_comments,
        avg_upvote_ratio=round(like_ratio, 3),
        avg_sentiment=round(sentiment, 3),
        total_views=total_views,
        total_engagement=total_engagement,
        has_hot_content=has_hot,
        has_controversial_content=has_controversial,
        fetch_time=datetime.now(timezone.utc).isoformat(),
        raw_sample_count=video_count,
    )
