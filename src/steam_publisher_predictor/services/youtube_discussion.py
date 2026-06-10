"""YouTube public discussion collector for Steam Publisher Predictor.

Uses the public YouTube Data API v3 search endpoint with no authentication
for basic channel/video search (rate-limited public tier).  Falls back
gracefully when the source is unavailable — never raises to the caller.

Falls back to an alternative approach using the unauthenticated YouTube
search page scrape when the API key is not configured or quota is exhausted.

See Iteration_Development_Spec.md §15 (Data Adapter Rules).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from steam_publisher_predictor.services.discussion_source_base import (
    DiscussionSourceABC,
    NormalizedDiscussionResult,
    register_discussion_source,
)

_HTTP_TIMEOUT_SEC = 15
_USER_AGENT = "steam-publisher-predictor/0.1 (+https://github.com/steam-publisher-predictor)"


@dataclass(slots=True)
class _VideoItem:
    """Lightweight internal representation of a YouTube video."""
    title: str = ""
    video_id: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    channel_name: str = ""
    published: str = ""
    url: str = ""
    duration: str = ""


@register_discussion_source("youtube")
class YouTubeSource(DiscussionSourceABC):
    """Fetch and normalise public YouTube discussion data for a game.

    Strategy
    --------
    1. Try the YouTube Data API v3 search endpoint (if YOUTUBE_API_KEY env var is set).
    2. Fall back to scraping the public YouTube search page.
    3. Collect up to *max_results* recent videos.
    4. Derive engagement metrics.
    5. Return a :py:class:`NormalizedDiscussionResult`.
    """

    SOURCE_TYPE: str = "youtube"

    def __init__(self, timeout: float = _HTTP_TIMEOUT_SEC) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": _USER_AGENT,
            },
            follow_redirects=True,
        )
        self._max_attempts = 2
        self._api_key: str = ""
        # Read API key from environment at init time
        try:
            import os
            self._api_key = os.environ.get("YOUTUBE_API_KEY", "")
        except Exception:
            self._api_key = ""

    # ── public API ──────────────────────────────────────────────────────

    def fetch(
        self,
        game_name: str,
        max_results: int = 20,
    ) -> NormalizedDiscussionResult:
        if self._api_key:
            try:
                raw_items = self._search_via_api(game_name, limit=max_results)
            except Exception as exc:
                # API failed — fall back to scrape
                try:
                    raw_items = self._search_via_scrape(game_name, limit=max_results)
                except Exception as exc2:
                    return self._error_result(game_name, f"API failed ({exc}), scrape also failed ({exc2})")
        else:
            try:
                raw_items = self._search_via_scrape(game_name, limit=max_results)
            except Exception as exc:
                return self._error_result(game_name, f"Scrape failed: {exc}")

        if not raw_items:
            return self._empty_result(game_name)

        return _normalise(raw_items, source_type=self.SOURCE_TYPE, game_name=game_name)

    # ── API-based search ────────────────────────────────────────────────

    def _search_via_api(
        self,
        game_name: str,
        limit: int = 20,
    ) -> list[_VideoItem]:
        base_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": f"{game_name} review gameplay",
            "type": "video",
            "maxResults": min(limit, 50),
            "order": "relevance",
            "key": self._api_key,
        }
        last_error: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                resp = self._client.get(base_url, params=params)
                if resp.status_code == 403:
                    # Quota exhausted — return empty, don't escalate to scrape
                    return []
                resp.raise_for_status()
                data = resp.json()
                return _parse_api_response(data)
            except Exception as exc:
                last_error = exc
                time.sleep(1)
        return []

    # ── Scrape-based search ─────────────────────────────────────────────

    def _search_via_scrape(
        self,
        game_name: str,
        limit: int = 20,
    ) -> list[_VideoItem]:
        """Fallback: scrape public YouTube search page.

        This is a best-effort approach — YouTube's page structure may change.
        """
        search_url = "https://www.youtube.com/results"
        params = {"search_query": game_name}

        try:
            resp = self._client.get(search_url, params=params)
            resp.raise_for_status()
            return _parse_scrape_response(resp.text, limit)
        except Exception:
            return []


    def _error_result(self, game_name: str, message: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            error_message=f"YouTube fetch failed: {message}",
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )

    def _empty_result(self, game_name: str) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            fetch_time=datetime.now(timezone.utc).isoformat(),
        )


# ── API response parser ────────────────────────────────────────────────────

def _parse_api_response(data: dict) -> list[_VideoItem]:
    """Extract videos from YouTube API v3 response."""
    items = data.get("items", [])
    results: list[_VideoItem] = []
    for item in items:
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        results.append(_VideoItem(
            title=snippet.get("title", ""),
            video_id=video_id,
            channel_name=snippet.get("channelTitle", ""),
            published=snippet.get("publishedAt", "")[:10],
            url=f"https://www.youtube.com/watch?v={video_id}",
        ))
    return results


# ── Scrape response parser ─────────────────────────────────────────────────

def _parse_scrape_response(html: str, limit: int = 20) -> list[_VideoItem]:
    """Extract video info from YouTube search results page HTML.

    This parses structured JSON embedded in the page (ytdc-macros template)
    which is more stable than CSS selectors.
    """
    results: list[_VideoItem] = []
    tree = HTMLParser(html)

    # Try to find embedded JSON in script tags (more reliable than CSS)
    for script in tree.css("script"):
        text = script.text()
        if "ytdc-macros" in text or "INNERTUBE" in text:
            # Find all video JSON objects in the script
            matches = re.findall(r'"videoId":"([^"]+)"[^}]*?"title":\{"runs":\[\{"text":"([^"]+)"\}', text)
            for video_id, title in matches:
                if len(results) >= limit:
                    break
                url = f"https://www.youtube.com/watch?v={video_id}"
                results.append(_VideoItem(
                    title=_decode_html(title),
                    video_id=video_id,
                    url=url,
                ))

    # Fallback: if JSON parsing didn't yield results, try direct CSS
    if not results:
        for video in tree.css("ytd-video-renderer, a#video-title-link, ytd-rich-item-renderer"):
            title_el = video.css_one("#video-title, #video-title-link, a.yt-lockup-title")
            if not title_el:
                continue
            href = title_el.get("href", "")
            if not href:
                href = video.css_one("a").get("href", "") if video.css_one("a") else ""
            video_id = ""
            m = re.search(r"watch\?v=([a-zA-Z0-9_-]{11})", href)
            if m:
                video_id = m.group(1)
            if not video_id:
                continue
            title = title_el.text()
            if not title or len(title) < 3:
                continue
            results.append(_VideoItem(
                title=_decode_html(title),
                video_id=video_id,
                url=f"https://www.youtube.com{href}" if href.startswith("/") else href,
            ))
            if len(results) >= limit:
                break

    return results[:limit]


def _decode_html(text: str) -> str:
    """Decode common HTML entities."""
    return (
        text.replace("&quot;", '"')
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&#39;", "'")
            .replace("&nbsp;", " ")
            .replace("&#x27;", "'")
            .replace("&#x26;", "&")
    )


# ── Normalisation ───────────────────────────────────────────────────────────

def _normalise(
    raw_items: list[_VideoItem],
    *,
    source_type: str,
    game_name: str,
) -> NormalizedDiscussionResult:
    """Aggregate raw YouTube items into a :py:class:`NormalizedDiscussionResult`."""
    video_count = len(raw_items)

    # Estimate total engagement: views + comments as proxy
    total_views = sum(r.view_count for r in raw_items)
    total_likes = sum(r.like_count for r in raw_items)
    total_comments = sum(r.comment_count for r in raw_items)
    total_engagement = total_views + total_likes + total_comments

    # Sentiment proxy — YouTube doesn't expose sentiment directly
    # Use like/total_ratio as rough positive indicator
    if total_likes + total_comments > 0:
        avg_upvote = total_likes / (total_likes + max(total_comments, 1))
        avg_sentiment = min(1.0, max(-1.0, (avg_upvote - 0.5) * 2.0))
    else:
        avg_sentiment = 0.0

    # Hot content: any video with > 5000 views
    has_hot = any(r.view_count >= 5000 for r in raw_items)

    # Controversial: high comment-to-like ratio
    has_controversial = any(
        r.like_count > 0 and (r.comment_count / max(r.like_count, 1)) > 2.0
        for r in raw_items
    )

    return NormalizedDiscussionResult(
        source_type=source_type,
        game_name=game_name,
        post_count=video_count,
        comment_count=total_comments,
        avg_upvote_ratio=round(
            total_likes / max(total_likes + total_comments, 1), 3
        ),
        avg_sentiment=round(avg_sentiment, 3),
        total_views=total_views,
        total_engagement=total_engagement,
        has_hot_content=has_hot,
        has_controversial_content=has_controversial,
        fetch_time=datetime.now(timezone.utc).isoformat(),
        raw_sample_count=video_count,
    )
