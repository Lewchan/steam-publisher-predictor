"""QA-2026-001 TI-009: steamdb_client.py 测试

Quinn-QA 2026/06/11 迭代执行
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from steam_publisher_predictor.services import steamdb_client
from steam_publisher_predictor.services.steamdb_client import (
    SteamDbClient,
    SteamDbClientError,
    _extract_first_float,
    _extract_first_int,
    _normalize_text,
    _parse_steamdb_html,
)


# ── 1. _normalize_text ──────────────────────────────────────────────


class TestNormalizeText:
    """TC-TI009-022 ~ TC-TI009-024"""

    def test_remove_script_tags(self):
        """TC-TI009-022: 移除script标签"""
        html = '<html><script>var x = 1;</script><body>hello</body></html>'
        result = _normalize_text(html)
        assert "var x" not in result
        assert "script" not in result.lower()

    def test_remove_style_tags(self):
        """TC-TI009-023: 移除style标签"""
        html = '<html><style>body{color:red}</style><body>hello</body></html>'
        result = _normalize_text(html)
        assert "color:red" not in result
        assert "style" not in result.lower()

    def test_merge_whitespace(self):
        """TC-TI009-024: 合并空白"""
        html = "<html>  hello    world   </html>"
        result = _normalize_text(html)
        # 多个空格应合并为单个
        assert "hello   world" not in result
        assert "hello world" in result

    def test_strip_html_tags(self):
        """TC-TI009-024b: 移除所有HTML标签"""
        html = '<div class="test">Hello <b>World</b></div>'
        result = _normalize_text(html)
        assert "<" not in result
        assert ">" not in result
        assert "Hello" in result
        assert "World" in result

    def test_multiline_script(self):
        """TC-TI009-022b: 多行script块移除"""
        html = '<script>\nline1\nline2\n</script>'
        result = _normalize_text(html)
        assert "line1" not in result
        assert "line2" not in result


# ── 2. _extract_first_int ───────────────────────────────────────────


class TestExtractFirstInt:
    """TC-TI009-025 ~ TC-TI009-027"""

    def test_comma_separated_number(self):
        """TC-TI009-025: 带千分位逗号数字提取"""
        text = "12,345 players right now"
        result = _extract_first_int(text, r"([\d,]+)\s+players")
        assert result == 12345

    def test_no_match_returns_zero(self):
        """TC-TI009-026: 无匹配返回0"""
        text = "no numbers here at all"
        result = _extract_first_int(text, r"(\d+)")
        assert result == 0

    def test_case_insensitive(self):
        """TC-TI009-027: 大小写不敏感"""
        text = "24-HOUR PEAK is 5000"
        result = _extract_first_int(text, r"(\d+)\s+24-hour peak", )
        assert result == 5000

    def test_first_match_only(self):
        """TC-TI009-027b: 只提取第一个匹配"""
        text = "100 players, 200 peak, 300 all-time"
        result = _extract_first_int(text, r"(\d+) players")
        assert result == 100


# ── 3. _extract_first_float ─────────────────────────────────────────


class TestExtractFirstFloat:
    """TC-TI009-028 ~ TC-TI009-029"""

    def test_normal_float(self):
        """TC-TI009-028: 正常浮点提取"""
        text = "87.5% SteamDB Rating"
        result = _extract_first_float(text, r"([\d.]+)%")
        assert result == 87.5

    def test_no_match_returns_zero(self):
        """TC-TI009-029: 无匹配返回0.0"""
        text = "no floats here"
        result = _extract_first_float(text, r"([\d.]+)")
        assert result == 0.0

    def test_integer_like_float(self):
        """TC-TI009-028b: 整数值作为浮点返回"""
        text = "100% something"
        result = _extract_first_float(text, r"([\d.]+)%")
        assert result == 100.0


# ── 4. _parse_steamdb_html ─────────────────────────────────────────


class TestParseSteamdbHtml:
    """TC-TI009-030 ~ TC-TI009-042"""

    def _make_html(self, **kwargs):
        """Build a mock SteamDB HTML page with given stats."""
        lines = []
        lines.append("<html><body>")
        if kwargs.get("current_players"):
            lines.append(f"{kwargs['current_players']} players right now")
        if kwargs.get("peak_24h"):
            lines.append(f"{kwargs['peak_24h']} 24-hour peak")
        if kwargs.get("all_time_peak"):
            lines.append(f"{kwargs['all_time_peak']} all-time peak")
        if kwargs.get("followers"):
            lines.append(f"{kwargs['followers']} followers")
        if kwargs.get("reviews"):
            lines.append(f"{kwargs['reviews']} reviews")
        if kwargs.get("steamdb_rating"):
            lines.append(f"{kwargs['steamdb_rating']}% SteamDB Rating")
        if kwargs.get("positive_reviews"):
            lines.append(f"{kwargs['positive_reviews']} 90.5% positive reviews")
        if kwargs.get("negative_reviews"):
            lines.append(f"{kwargs['negative_reviews']} 9.5% negative reviews")
        if kwargs.get("daily_active_users_rank"):
            lines.append(f"#{kwargs['daily_active_users_rank']} in daily active users")
        if kwargs.get("top_sellers_rank"):
            lines.append(f"#{kwargs['top_sellers_rank']} in top sellers")
        if kwargs.get("wishlist_activity_rank"):
            lines.append(f"#{kwargs['wishlist_activity_rank']} in wishlist activity")
        if kwargs.get("last_30_days_peak"):
            lines.append(f"Last 30 days {kwargs['last_30_days_peak']}")
        lines.append("</body></html>")
        return "\n".join(lines)

    # ── 各字段单独测试 ──

    def test_current_players(self):
        """TC-TI009-030: current_players 提取"""
        html = self._make_html(current_players=12345)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.current_players == 12345

    def test_peak_24h(self):
        """TC-TI009-031: peak_24h 提取"""
        html = self._make_html(peak_24h=15000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.peak_24h == 15000

    def test_all_time_peak(self):
        """TC-TI009-032: all_time_peak 提取"""
        html = self._make_html(all_time_peak=50000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.all_time_peak == 50000

    def test_followers(self):
        """TC-TI009-033: followers 提取"""
        html = self._make_html(followers=8000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.followers == 8000

    def test_reviews(self):
        """TC-TI009-034: reviews 提取"""
        html = self._make_html(reviews=25000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.reviews == 25000

    def test_steamdb_rating(self):
        """TC-TI009-035: steamdb_rating 提取"""
        html = self._make_html(steamdb_rating=92.3)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.steamdb_rating == 92.3

    def test_positive_negative_reviews(self):
        """TC-TI009-036: positive/negative reviews 提取"""
        html = self._make_html(positive_reviews=22500, negative_reviews=2500)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.positive_reviews == 22500
        assert stats.negative_reviews == 2500

    def test_daily_active_users_rank(self):
        """TC-TI009-037: daily_active_users_rank 提取"""
        html = self._make_html(daily_active_users_rank=150)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.daily_active_users_rank == 150

    def test_top_sellers_rank(self):
        """TC-TI009-038: top_sellers_rank 提取"""
        html = self._make_html(top_sellers_rank=25)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.top_sellers_rank == 25

    def test_wishlist_activity_rank(self):
        """TC-TI009-039: wishlist_activity_rank 提取"""
        html = self._make_html(wishlist_activity_rank=10)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.wishlist_activity_rank == 10

    def test_last_30_days_peak(self):
        """TC-TI009-040: last_30_days_peak 提取"""
        html = self._make_html(last_30_days_peak=30000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.last_30_days_peak == 30000

    # ── 组合与边界测试 ──

    def test_has_data_true(self):
        """TC-TI009-041: has_data=True (有有效数据)"""
        html = self._make_html(current_players=1000)
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.has_data is True

    def test_has_data_false(self):
        """TC-TI009-042: has_data=False (全0)"""
        html = self._make_html()  # 没有任何字段
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.has_data is False

    def test_url_passed_to_stats(self):
        """TC-TI009-042b: URL 正确传递到 SteamDbStats"""
        url = "https://steamdb.info/app/42/charts/"
        stats = _parse_steamdb_html("<html></html>", url)
        assert stats.url == url

    def test_all_fields_together(self):
        """TC-TI009-042b: 所有字段同时存在"""
        html = self._make_html(
            current_players=12345,
            peak_24h=15000,
            all_time_peak=50000,
            followers=8000,
            reviews=25000,
            steamdb_rating=92.3,
            positive_reviews=22500,
            negative_reviews=2500,
            daily_active_users_rank=150,
            top_sellers_rank=25,
            wishlist_activity_rank=10,
            last_30_days_peak=30000,
        )
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.current_players == 12345
        assert stats.peak_24h == 15000
        assert stats.all_time_peak == 50000
        assert stats.followers == 8000
        assert stats.reviews == 25000
        assert stats.steamdb_rating == 92.3
        assert stats.positive_reviews == 22500
        assert stats.negative_reviews == 2500
        assert stats.daily_active_users_rank == 150
        assert stats.top_sellers_rank == 25
        assert stats.wishlist_activity_rank == 10
        assert stats.last_30_days_peak == 30000


# ── 5. IP 封禁与 Cloudflare 检测 ──────────────────────────────────


class TestSteamdbDetection:
    """TC-TI009-043 ~ TC-TI009-044"""

    def test_ip_ban_detection(self):
        """TC-TI009-043: IP封禁检测"""
        html = "<html>You have been banned on steamdb</html>"
        with pytest.raises(SteamDbClientError, match="banned"):
            _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")

    def test_cloudflare_detection(self):
        """TC-TI009-044: Cloudflare检测"""
        html = "<html>checking if the site connection is secure. Cloudflare verify you are human</html>"
        with pytest.raises(SteamDbClientError, match="challenge"):
            _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")

    def test_cloudflare_no_challenge(self):
        """TC-TI009-044b: 仅提到Cloudflare但无挑战页面时不抛异常"""
        html = "<html>Powered by Cloudflare</html>"
        # 不应抛异常
        stats = _parse_steamdb_html(html, "https://steamdb.info/app/42/charts/")
        assert stats.has_data is False


# ── 6. SteamDbClient ──────────────────────────────────────────────


class TestSteamDbClient:
    """TC-TI009-045 ~ TC-TI009-046"""

    def test_default_timeout(self):
        """TC-TI009-045: 默认超时25000ms"""
        client = SteamDbClient()
        assert client._timeout_ms == 25000

    def test_custom_timeout(self):
        """TC-TI009-046: 自定义超时"""
        client = SteamDbClient(timeout_ms=5000)
        assert client._timeout_ms == 5000

    @patch("steam_publisher_predictor.services.steamdb_client.SteamDbHttpClient")
    def test_fetch_stats_delegates_to_http_client(self, mock_http_cls):
        """TC-TI009-046b: fetch_stats 委托给 HTTP 客户端"""
        from steam_publisher_predictor.services.steamdb_http import SteamDbHttpClient

        # Mock: HTTP层返回HTML
        mock_http = MagicMock()
        mock_http._fetch_html.return_value = "<html>100 players right now</html>"
        SteamDbHttpClient.return_value = mock_http

        client = SteamDbClient()
        stats = client.fetch_stats(42)

        # 验证HTTP客户端被调用
        SteamDbHttpClient.assert_called_once()
        assert stats.current_players == 100

    @patch("steam_publisher_predictor.services.steamdb_client.SteamDbHttpClient")
    def test_fetch_stats_raises_on_http_failure(self, mock_http_cls):
        """TC-TI009-046c: HTTP层失败抛出SteamDbClientError"""
        from steam_publisher_predictor.services.steamdb_http import SteamDbHttpClientError

        mock_http = MagicMock()
        mock_http._fetch_html.side_effect = SteamDbHttpClientError("HTTP failed")
        SteamDbHttpClient.return_value = mock_http

        client = SteamDbClient()
        with pytest.raises(SteamDbClientError):
            client.fetch_stats(42)
