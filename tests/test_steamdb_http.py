"""Tests for the SteamDB HTTP-only adapter."""

from __future__ import annotations

import pytest

from steam_publisher_predictor.models import SteamDbStats
from steam_publisher_predictor.services.steamdb_http import (
    SteamDbHttpClientError,
    _extract_first_float,
    _extract_first_int,
    _normalize_text,
    _parse_steamdb_html,
)


class TestNormalizeText:
    """Sanity checks for the HTML→text normalizer."""

    def test_removes_script_tags(self):
        html = "<script>alert(1)</script><p>Hello</p>"
        result = _normalize_text(html)
        assert "alert" not in result

    def test_removes_style_tags(self):
        html = "<style>.x{color:red}</style><p>Hello</p>"
        result = _normalize_text(html)
        assert "color" not in result

    def test_flattens_tags(self):
        html = "<div><span>Hello</span></div>"
        result = _normalize_text(html)
        assert "Hello" in result


class TestExtractIntFloat:
    """Pattern extraction helpers."""

    def test_extract_int_with_commas(self):
        result = _extract_first_int("42,000 players", r"([\d,]+)\s+players")
        assert result == 42000

    def test_extract_int_without_commas(self):
        result = _extract_first_int("500 followers", r"([\d,]+)\s+followers")
        assert result == 500

    def test_extract_int_no_match(self):
        result = _extract_first_int("nothing here", r"([\d,]+)")
        assert result == 0

    def test_extract_float(self):
        result = _extract_first_float("97.5% SteamDB Rating", r"([\d.]+)%")
        assert result == pytest.approx(97.5)

    def test_extract_float_no_match(self):
        result = _extract_first_float("nothing", r"([\d.]+)%")
        assert result == pytest.approx(0.0)


class TestParseSteamDbHtml:
    """HTML → SteamDbStats conversion tests with known fixtures."""

    _MINIMAL_HTML = """
    <html>
    <body>
        <p>1,234 players right now</p>
        <p>2,000 24-hour peak</p>
        <p>5,000 all-time peak</p>
        <p>800 followers</p>
        <p>3,000 reviews</p>
        <p>95.0% SteamDB Rating</p>
        <p>2,500 95.0% positive reviews</p>
        <p>150 5.0% negative reviews</p>
        <p>#42 in daily active users</p>
        <p>#100 in top sellers</p>
        <p>#500 in wishlist activity</p>
        <p>Last 30 days 1,500</p>
    </body>
    </html>
    """

    def test_parses_all_fields(self):
        stats = _parse_steamdb_html(self._MINIMAL_HTML, "https://steamdb.info/app/12345/charts/")

        assert stats.current_players == 1234
        assert stats.peak_24h == 2000
        assert stats.all_time_peak == 5000
        assert stats.followers == 800
        assert stats.reviews == 3000
        assert stats.steamdb_rating == pytest.approx(95.0)
        assert stats.positive_reviews == 2500
        assert stats.negative_reviews == 150
        assert stats.daily_active_users_rank == 42
        assert stats.top_sellers_rank == 100
        assert stats.wishlist_activity_rank == 500
        assert stats.last_30_days_peak == 1500
        assert stats.has_data is True

    def test_empty_html(self):
        stats = _parse_steamdb_html("<html><body></body></html>", "https://steamdb.info/app/0/charts/")

        assert stats.has_data is False
        assert stats.current_players == 0
        assert stats.steamdb_rating == pytest.approx(0.0)

    def test_blocked_by_steamdb(self):
        html = "<html><body>You have been banned on SteamDB.</body></html>"
        with pytest.raises(SteamDbHttpClientError, match="blocked"):
            _parse_steamdb_html(html, "https://steamdb.info/app/0/charts/")

    def test_blocked_by_cloudflare(self):
        html = "<html><body>cloudflare - verify you are human</body></html>"
        with pytest.raises(SteamDbHttpClientError, match="challenge"):
            _parse_steamdb_html(html, "https://steamdb.info/app/0/charts/")
