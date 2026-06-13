# Webber 2026/06/13 迭代: SteamDB HTTP 适配器增强 — 重试间隔 + 速率限制检测 + 超时配置
"""Lightweight SteamDB HTTP-only adapter.

Parses SteamDB app charts page without Playwright.
Falls back to ``SteamDbClient`` (Playwright) when HTTP parsing fails.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import httpx

from steam_publisher_predictor.models import SteamDbStats

if TYPE_CHECKING:
    from steam_publisher_predictor.services.steamdb_client import SteamDbClient

STATS_URL = "https://steamdb.info/app/{app_id}/charts/"
_HTTP_TIMEOUT_SEC = 20
_HTTP_MAX_RETRIES = 3
_HTTP_RETRY_DELAY_SEC = 2.0  # Delay between retries to avoid rate limiting


class SteamDbHttpClientError(RuntimeError):
    """Raised when the SteamDB HTTP adapter cannot fetch or parse data."""


class SteamDbHttpClient:
    """HTTP-only SteamDB adapter that avoids Playwright overhead."""

    def __init__(self, timeout: float = _HTTP_TIMEOUT_SEC) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "steam-publisher-predictor/0.1 "
                    "(+https://github.com/steam-publisher-predictor)"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=True,
            trust_env=False,
        )
        self._max_attempts = _HTTP_MAX_RETRIES
        self._retry_delay = _HTTP_RETRY_DELAY_SEC

    def fetch_stats(self, app_id: int) -> SteamDbStats:
        url = STATS_URL.format(app_id=app_id)
        html = self._fetch_html(url)
        stats = _parse_steamdb_html(html, url)
        return stats

    def _fetch_html(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = self._client.get(url)
                # Rate limit detection: 429 Too Many Requests
                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    delay = float(retry_after) if retry_after else self._retry_delay * (attempt + 1)
                    time.sleep(delay)
                    last_error = httpx.HTTPStatusError(
                        f"Rate limited (429), retrying after {delay:.1f}s",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                return response.text
            except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ConnectError) as exc:
                last_error = exc
                if attempt < self._max_attempts - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                continue
            except httpx.HTTPStatusError as exc:
                # 5xx server errors are retryable; 4xx are not
                if 500 <= exc.response.status_code < 600 and attempt < self._max_attempts - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                    last_error = exc
                    continue
                last_error = exc
                break

        if last_error is not None:
            raise SteamDbHttpClientError(f"SteamDB HTTP request failed after retries: {last_error}") from last_error
        raise SteamDbHttpClientError("SteamDB HTTP request failed for an unknown reason.")


def _parse_steamdb_html(html: str, url: str) -> SteamDbStats:
    """Parse SteamDB charts page HTML into a :class:`SteamDbStats` record."""
    text = _normalize_text(html)
    lowered = text.lower()
    if "you have been banned on steamdb" in lowered:
        raise SteamDbHttpClientError("SteamDB blocked this IP address.")
    if "checking if the site connection is secure" in lowered or ("cloudflare" in lowered and "verify you are human" in lowered):
        raise SteamDbHttpClientError("SteamDB presented a bot or challenge page.")

    stats = SteamDbStats(url=url)

    stats.current_players = _extract_first_int(text, r"([\d,]+)\s+players right now")
    stats.peak_24h = _extract_first_int(text, r"([\d,]+)\s+24-hour peak")
    stats.all_time_peak = _extract_first_int(text, r"([\d,]+)\s+all-time peak")
    stats.followers = _extract_first_int(text, r"([\d,]+)\s+followers")
    stats.reviews = _extract_first_int(text, r"([\d,]+)\s+reviews")
    stats.steamdb_rating = _extract_first_float(text, r"([\d.]+)%\s+SteamDB Rating")
    stats.positive_reviews = _extract_first_int(text, r"([\d,]+)\s+[\d.]+%\s+positive reviews")
    stats.negative_reviews = _extract_first_int(text, r"([\d,]+)\s+[\d.]+%\s+negative reviews")
    stats.daily_active_users_rank = _extract_first_int(text, r"#([\d,]+)\s+in daily active users")
    stats.top_sellers_rank = _extract_first_int(text, r"#([\d,]+)\s+in top sellers")
    stats.wishlist_activity_rank = _extract_first_int(text, r"#([\d,]+)\s+in wishlist activity")
    stats.last_30_days_peak = _extract_first_int(text, r"Last 30 days\s+([\d,]+)")
    stats.has_data = any(
        [
            stats.current_players,
            stats.peak_24h,
            stats.all_time_peak,
            stats.followers,
            stats.steamdb_rating,
        ]
    )
    return stats


def _normalize_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_first_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))


def _extract_first_float(text: str, pattern: str) -> float:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return 0.0
    return float(match.group(1))
