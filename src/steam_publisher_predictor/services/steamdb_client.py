from __future__ import annotations

import re

from steam_publisher_predictor.models import SteamDbStats


class SteamDbClientError(RuntimeError):
    """Raised when SteamDB data cannot be fetched."""


class SteamDbClient:
    APP_CHARTS_URL = "https://steamdb.info/app/{app_id}/charts/"

    def __init__(self, timeout_ms: int = 25000) -> None:
        self._timeout_ms = timeout_ms

    def fetch_stats(self, app_id: int) -> SteamDbStats:
        url = self.APP_CHARTS_URL.format(app_id=app_id)
        html = self._fetch_html(url)
        stats = _parse_steamdb_html(html, url)
        return stats

    def _fetch_html(self, url: str) -> str:
        from playwright.sync_api import sync_playwright

        last_error: Exception | None = None
        with sync_playwright() as playwright:
            for launcher in _browser_launchers(playwright):
                try:
                    browser = launcher()
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                    page.wait_for_timeout(1200)
                    html = page.content()
                    browser.close()
                    return html
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    try:
                        browser.close()
                    except Exception:  # noqa: BLE001
                        pass

        raise SteamDbClientError(f"SteamDB browser fetch failed: {last_error}")


def _browser_launchers(playwright):
    launchers = []
    launchers.append(lambda: playwright.chromium.launch(channel="msedge", headless=True))
    launchers.append(lambda: playwright.chromium.launch(channel="chrome", headless=True))
    launchers.append(lambda: playwright.chromium.launch(headless=True))
    return launchers


def _parse_steamdb_html(html: str, url: str) -> SteamDbStats:
    text = _normalize_text(html)
    lowered = text.lower()
    if "you have been banned on steamdb" in lowered:
        raise SteamDbClientError("SteamDB blocked this IP address.")
    if "checking if the site connection is secure" in lowered or "cloudflare" in lowered and "verify you are human" in lowered:
        raise SteamDbClientError("SteamDB presented a bot or challenge page.")

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
