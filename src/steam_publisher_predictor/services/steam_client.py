from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from steam_publisher_predictor.models import SteamGame


class SteamClientError(RuntimeError):
    """Raised when Steam data cannot be fetched or parsed."""


class SteamClient:
    SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
    APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
    APP_REVIEWS_URL = "https://store.steampowered.com/appreviews/{app_id}"
    APP_PAGE_URL = "https://store.steampowered.com/app/{app_id}/"

    def __init__(self, timeout: float = 20.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "steam-publisher-predictor/0.1",
                "Accept": "application/json,text/plain,*/*",
            },
            follow_redirects=True,
            trust_env=False,
        )

    def search(self, query: str, count: int = 10) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            return []

        response = self._client.get(
            self.SEARCH_URL,
            params={"term": query, "l": "english", "cc": "US"},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", [])

        matches: list[dict[str, object]] = []
        for item in items[:count]:
            matches.append(
                {
                    "app_id": int(item.get("id", 0)),
                    "name": str(item.get("name", "")),
                    "price_usd": float(item.get("price", {}).get("final", 0)) / 100.0,
                }
            )
        return matches

    def resolve_app_id(self, query_or_url: str) -> int:
        query_or_url = query_or_url.strip()
        if query_or_url.isdigit():
            return int(query_or_url)

        if "store.steampowered.com/app/" in query_or_url:
            parts = [part for part in urlparse(query_or_url).path.split("/") if part]
            if len(parts) >= 2 and parts[0] == "app" and parts[1].isdigit():
                return int(parts[1])

        matches = self.search(query_or_url, count=1)
        if not matches:
            raise SteamClientError("No Steam app matched the provided game name.")
        return int(matches[0]["app_id"])

    def fetch_game(self, query_or_url: str) -> SteamGame:
        app_id = self.resolve_app_id(query_or_url)
        details = self._fetch_details(app_id)
        review_summary = self._fetch_review_summary(app_id)
        steam_tags = self._fetch_store_tags(app_id)
        return self._to_game(app_id, details, review_summary, steam_tags)

    def _fetch_details(self, app_id: int) -> dict[str, object]:
        response = self._client.get(
            self.APP_DETAILS_URL,
            params={"appids": app_id, "l": "english", "cc": "US"},
        )
        response.raise_for_status()
        payload = response.json()
        if str(app_id) not in payload or not payload[str(app_id)].get("success"):
            raise SteamClientError(f"Steam app details were not available for app {app_id}.")
        return payload[str(app_id)]["data"]

    def _fetch_review_summary(self, app_id: int) -> dict[str, object]:
        response = self._client.get(
            self.APP_REVIEWS_URL.format(app_id=app_id),
            params={
                "json": 1,
                "language": "all",
                "purchase_type": "all",
                "filter": "summary",
                "day_range": 3650,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("query_summary", {})

    def _to_game(
        self,
        app_id: int,
        details: dict[str, object],
        review_summary: dict[str, object],
        steam_tags: list[str],
    ) -> SteamGame:
        release_date = details.get("release_date", {}) or {}
        price_overview = details.get("price_overview", {}) or {}
        metacritic = details.get("metacritic", {}) or {}

        return SteamGame(
            app_id=app_id,
            name=str(details.get("name", "")),
            url=f"https://store.steampowered.com/app/{app_id}/",
            developer_names=[str(value) for value in details.get("developers", [])],
            publisher_names=[str(value) for value in details.get("publishers", [])],
            genres=[str(item.get("description", "")) for item in details.get("genres", [])],
            steam_tags=steam_tags,
            categories=[str(item.get("description", "")) for item in details.get("categories", [])],
            supported_languages=_split_languages(str(details.get("supported_languages", ""))),
            price_usd=float(price_overview.get("final", 0)) / 100.0,
            review_count=int(review_summary.get("total_reviews", 0)),
            review_score=float(review_summary.get("review_score", 0)),
            metacritic_score=int(metacritic.get("score", 0) or 0),
            dlc_count=len(details.get("dlc", []) or []),
            required_age=int(details.get("required_age", 0) or 0),
            has_demo=bool(details.get("demos")),
            has_achievements=bool(details.get("achievements")),
            is_free=bool(details.get("is_free")),
            coming_soon=bool(release_date.get("coming_soon")),
            release_date=_normalize_release_date(str(release_date.get("date", ""))),
            short_description=str(details.get("short_description", "")),
        )

    def _fetch_store_tags(self, app_id: int) -> list[str]:
        response = self._client.get(self.APP_PAGE_URL.format(app_id=app_id), params={"l": "english", "cc": "US"})
        response.raise_for_status()
        parser = HTMLParser(response.text)

        tags: list[str] = []
        for node in parser.css(".app_tag"):
            label = " ".join(node.text(separator=" ").split())
            if label and label != "+" and label not in tags:
                tags.append(label)
        return tags[:20]


def _split_languages(raw: str) -> list[str]:
    cleaned = raw.replace("<strong>*</strong>", "").replace("<br>", ",")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def _normalize_release_date(value: str) -> str | None:
    if not value:
        return None

    for fmt in ("%d %b, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    current_year = datetime.now(UTC).year
    for fmt in ("%d %b", "%b %d"):
        try:
            parsed = datetime.strptime(f"{value}, {current_year}", f"{fmt}, %Y")
            return parsed.date().isoformat()
        except ValueError:
            continue

    return None
