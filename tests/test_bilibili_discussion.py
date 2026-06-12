"""QA-2026-001 TI-009: bilibili_discussion.py 测试

Quinn-QA 2026/06/11 迭代执行
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Import internal helpers by importing the module
import steam_publisher_predictor.services.bilibili_discussion as bili


# ── 1. _VideoItem dataclass ───────────────────────────────────────


class TestVideoItem:
    """TC-TI009-000: _VideoItem dataclass 基本验证"""

    def test_defaults(self):
        """TC-TI009-000: 所有字段有合理默认值"""
        v = bili._VideoItem()
        assert v.title == ""
        assert v.bvid == ""
        assert v.aid == 0
        assert v.view_count == 0
        assert v.danmaku_count == 0
        assert v.comment_count == 0
        assert v.like_count == 0
        assert v.coin_count == 0
        assert v.favorite_count == 0
        assert v.share_count == 0
        assert v.pubdate == ""
        assert v.owner_name == ""
        assert v.owner_mid == 0
        assert v.url == ""
        assert v.duration_seconds == 0
        assert v.description == ""
        assert v.ctime == 0
        assert v.pubtime == 0


# ── 2. _parse_duration ──────────────────────────────────────────────


class TestParseDuration:
    """TC-TI009-001 ~ TC-TI009-005"""

    def test_integer_seconds(self):
        """TC-TI009-001: 整数输入直接返回"""
        assert bili._parse_duration(120) == 120
        assert bili._parse_duration(0) == 0
        assert bili._parse_duration(3600) == 3600

    def test_float_seconds(self):
        """TC-TI009-004: 浮点数输入取整"""
        assert bili._parse_duration(120.7) == 120
        assert bili._parse_duration(0.5) == 0

    def test_mm_ss_string(self):
        """TC-TI009-002: MM:SS 字符串解析"""
        assert bili._parse_duration("01:30") == 90
        assert bili._parse_duration("10:00") == 600
        assert bili._parse_duration("00:00") == 0

    def test_hh_mm_ss_string(self):
        """TC-TI009-003: HH:MM:SS 字符串解析"""
        assert bili._parse_duration("01:00:00") == 3600
        assert bili._parse_duration("00:30:00") == 1800
        assert bili._parse_duration("02:15:30") == 8130

    def test_invalid_returns_zero(self):
        """TC-TI009-005: 无效输入返回0"""
        assert bili._parse_duration("invalid") == 0
        assert bili._parse_duration("1:2:3:4") == 0  # 4段
        assert bili._parse_duration(None) == 0


# ── 3. _extract_video ──────────────────────────────────────────────


class TestExtractVideo:
    """TC-TI009-006 ~ TC-TI009-007"""

    def test_valid_data_full_mapping(self):
        """TC-TI009-006: 有效数据完整映射"""
        raw = {
            "bvid": "BV1ab1234567",
            "aid": 12345,
            "title": "Test Game Review",
            "view": 50000,
            "danmaku": 200,
            "reply": 150,
            "like": 3000,
            "coins": 500,
            "favorites": 100,
            "share": 80,
            "pubdate": 1700000000,
            "author": "Tester",
            "mid": 98765,
            "duration": 600,
            "description": "A great review",
        }
        vid = bili._extract_video(raw)
        assert vid is not None
        assert vid.title == "Test Game Review"
        assert vid.bvid == "BV1ab1234567"
        assert vid.aid == 12345
        assert vid.view_count == 50000
        assert vid.like_count == 3000
        assert vid.coin_count == 500
        assert vid.owner_name == "Tester"
        assert vid.url == "https://www.bilibili.com/video/BV1ab1234567"

    def test_missing_bvid_and_aid_returns_none(self):
        """TC-TI009-007: 缺少bvid和aid返回None"""
        assert bili._extract_video({"title": "No ID"}) is None
        assert bili._extract_video({}) is None
        assert bili._extract_video(None) is None

    def test_pubdate_timestamp_conversion(self):
        """TC-TI009-006b: pubdate时间戳转换为日期字符串"""
        raw = {
            "bvid": "BV1test",
            "pubdate": 1700000000,
        }
        vid = bili._extract_video(raw)
        assert vid is not None
        assert vid.pubdate == "2023-11-14"  # UTC conversion

    def test_invalid_pubdate_returns_empty(self):
        """TC-TI009-007b: 无效时间戳返回空字符串"""
        raw = {
            "bvid": "BV1test",
            "pubdate": "not_a_timestamp",
        }
        vid = bili._extract_video(raw)
        assert vid.pubdate == ""


# ── 4. _parse_bilibili_search ──────────────────────────────────────


class TestParseBilibiliSearch:
    """TC-TI009-008 ~ TC-TI009-011"""

    def test_new_api_format(self):
        """TC-TI009-008: 新API格式 (data.result.video)"""
        data = {
            "data": {
                "result": {
                    "video": {
                        "numResults": 2,
                        "numResultsData": [
                            {
                                "bvid": "BV1aa",
                                "title": "Video A",
                                "view": 1000,
                                "danmaku": 10,
                                "reply": 5,
                                "like": 100,
                                "coins": 20,
                                "favorites": 10,
                                "share": 5,
                                "duration": 120,
                                "author": "CreatorA",
                                "mid": 111,
                                "pubdate": 1700000000,
                            },
                            {
                                "bvid": "BV1bb",
                                "title": "Video B",
                                "view": 2000,
                                "danmaku": 20,
                                "reply": 10,
                                "like": 200,
                                "coins": 30,
                                "favorites": 15,
                                "share": 8,
                                "duration": "05:30",
                                "author": "CreatorB",
                                "mid": 222,
                                "pubdate": 1700000001,
                            },
                        ],
                    }
                }
            }
        }
        results = bili._parse_bilibili_search(data, limit=20)
        assert len(results) == 2
        assert results[0].title == "Video A"
        assert results[1].title == "Video B"

    def test_old_api_format(self):
        """TC-TI009-009: 旧API格式 (data直接是result)"""
        data = {
            "data": {
                "video": {
                    "numResults": 1,
                    "result": [
                        {
                            "bvid": "BV1old",
                            "title": "Old Format Video",
                            "view": 500,
                            "danmaku": 5,
                            "reply": 3,
                            "like": 50,
                            "coins": 10,
                            "favorites": 5,
                            "share": 2,
                            "duration": 60,
                        }
                    ],
                }
            }
        }
        results = bili._parse_bilibili_search(data, limit=20)
        assert len(results) == 1
        assert results[0].title == "Old Format Video"

    def test_zero_results_returns_empty_list(self):
        """TC-TI009-010: numResults=0 返回空列表"""
        data = {"data": {"result": {"video": {"numResults": 0, "numResultsData": []}}}}
        results = bili._parse_bilibili_search(data)
        assert results == []

    def test_limit_truncation(self):
        """TC-TI009-011: 超过limit截断"""
        data = {
            "data": {
                "result": {
                    "video": {
                        "numResults": 10,
                        "numResultsData": [
                            {"bvid": f"BV{i}", "title": f"V{i}", "view": i} for i in range(10)
                        ],
                    }
                }
            }
        }
        results = bili._parse_bilibili_search(data, limit=3)
        assert len(results) == 3

    def test_empty_result_section(self):
        """TC-TI009-010b: 无result section返回空"""
        data = {"data": {}}
        results = bili._parse_bilibili_search(data)
        assert results == []


# ── 5. _normalise ──────────────────────────────────────────────────


class TestNormalise:
    """TC-TI009-012 ~ TC-TI009-018"""

    def _make_video(self, **kwargs):
        defaults = {
            "title": "Test",
            "bvid": "BV1test",
            "view_count": 0,
            "danmaku_count": 0,
            "comment_count": 0,
            "like_count": 0,
            "coin_count": 0,
            "favorite_count": 0,
            "share_count": 0,
            "duration_seconds": 0,
        }
        defaults.update(kwargs)
        return bili._VideoItem(**defaults)

    def test_basic_aggregation(self):
        """TC-TI009-012: 基本指标聚合计算"""
        items = [
            self._make_video(view_count=1000, like_count=100, comment_count=50,
                           danmaku_count=20, coin_count=30, favorite_count=10, share_count=5),
            self._make_video(view_count=500, like_count=50, comment_count=25,
                           danmaku_count=10, coin_count=15, favorite_count=5, share_count=3),
        ]
        result = bili._normalise(items, source_type="bilibili", game_name="TestGame")
        assert result.post_count == 2
        assert result.total_views == 1500
        assert result.total_engagement == 1500 + 150 + 75 + 30 + 45 + 15 + 8  # = 1823

    def test_like_ratio_calculation(self):
        """TC-TI009-013: 点赞率 likes/(likes+comments)"""
        items = [self._make_video(like_count=80, comment_count=20)]
        result = bili._normalise(items, source_type="bilibili", game_name="G")
        # 80/(80+20) = 0.8
        assert result.avg_upvote_ratio == 0.8

    def test_sentiment_value_range(self):
        """TC-TI009-015: 情感代理值域[-1, 1]"""
        # 高点赞低评论 → 正面
        items = [self._make_video(like_count=90, comment_count=10)]
        result = bili._normalise(items, source_type="bilibili", game_name="G")
        assert -1.0 <= result.avg_sentiment <= 1.0
        assert result.avg_sentiment > 0  # 正面

        # 低点赞高评论 → 负面
        items = [self._make_video(like_count=10, comment_count=90)]
        result = bili._normalise(items, source_type="bilibili", game_name="G")
        assert -1.0 <= result.avg_sentiment <= 1.0
        assert result.avg_sentiment < 0  # 负面

    def test_zero_likes_and_comments_sentiment_zero(self):
        """TC-TI009-016: 无评论无点赞时sentiment=0.0"""
        items = [self._make_video(like_count=0, comment_count=0)]
        result = bili._normalise(items, source_type="bilibili", game_name="G")
        assert result.avg_sentiment == 0.0

    def test_has_hot_content_threshold(self):
        """TC-TI009-017: has_hot_content: >1000播放量标记"""
        items = [
            self._make_video(view_count=500),
            self._make_video(view_count=2000),  # >1000
        ]
        result = bili._normalise(items, source_type="bilibili", game_name="G")
        assert result.has_hot_content is True

        items_no_hot = [self._make_video(view_count=500)]
        result_no_hot = bili._normalise(items_no_hot, source_type="bilibili", game_name="G")
        assert result_no_hot.has_hot_content is False

    def test_has_controversial_content(self):
        """TC-TI009-018: has_controversial: 评论/点赞比>3标记"""
        # 正常内容: 100 like, 20 comment → ratio=0.2
        items_normal = [self._make_video(like_count=100, comment_count=20)]
        result_normal = bili._normalise(items_normal, source_type="bilibili", game_name="G")
        assert result_normal.has_controversial_content is False

        # 争议内容: 10 like, 50 comment → ratio=5.0
        items_cont = [self._make_video(like_count=10, comment_count=50)]
        result_cont = bili._normalise(items_cont, source_type="bilibili", game_name="G")
        assert result_cont.has_controversial_content is True

    def test_empty_items_returns_empty_result(self):
        """TC-TI009-016b: 空列表返回空结果"""
        result = bili._normalise([], source_type="bilibili", game_name="G")
        assert result.post_count == 0
        assert result.total_views == 0

    def test_result_has_all_fields(self):
        """TC-TI009-012b: 结果包含所有必要字段"""
        items = [self._make_video(view_count=100, like_count=10, comment_count=5)]
        result = bili._normalise(items, source_type="bilibili", game_name="TestGame")
        assert result.source_type == "bilibili"
        assert result.game_name == "TestGame"
        assert isinstance(result.fetch_time, str)


# ── 6. BilibiliSource (mocked) ─────────────────────────────────────


class TestBilibiliSource:
    """TC-TI009-019 ~ TC-TI009-021"""

    @patch("steam_publisher_predictor.services.bilibili_discussion.httpx.Client")
    def test_fetch_network_error_returns_error_result(self, mock_httpx):
        """TC-TI009-019: 网络异常返回错误结果"""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_httpx.return_value = mock_client

        source = bili.BilibiliSource()
        result = source.fetch("NonExistentGame")

        assert result.source_type == "bilibili"
        assert result.game_name == "NonExistentGame"
        assert result.error_message is not None
        assert "Connection refused" in result.error_message

    @patch("steam_publisher_predictor.services.bilibili_discussion.httpx.Client")
    def test_fetch_empty_results_returns_empty_result(self, mock_httpx):
        """TC-TI009-020: 空搜索返回空结果"""
        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {
            "data": {"result": {"video": {"numResults": 0, "numResultsData": []}}}
        }

        source = bili.BilibiliSource()
        result = source.fetch("NonExistentGame")

        assert result.source_type == "bilibili"
        assert result.post_count == 0
        assert result.error_message is None

    @patch("steam_publisher_predictor.services.bilibili_discussion.httpx.Client")
    def test_fetch_retry_on_failure(self, mock_httpx):
        """TC-TI009-019b: 失败时重试"""
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
        ]
        mock_httpx.return_value = mock_client

        source = bili.BilibiliSource()
        result = source.fetch("TestGame")

        # 应该尝试2次
        assert mock_client.get.call_count == 2
        assert result.error_message is not None

    def test_error_result_format(self):
        """TC-TI009-019b: 错误结果格式验证"""
        source = bili.BilibiliSource()
        result = source._error_result("TestGame", "Test error")
        assert result.source_type == "bilibili"
        assert result.game_name == "TestGame"
        assert "Test error" in result.error_message

    def test_empty_result_format(self):
        """TC-TI009-020b: 空结果格式验证"""
        source = bili.BilibiliSource()
        result = source._empty_result("TestGame")
        assert result.source_type == "bilibili"
        assert result.game_name == "TestGame"
        assert result.post_count == 0
        assert result.error_message is None


# ── 7. 注册装饰器 ─────────────────────────────────────────────────


class TestRegisterDiscussionSource:
    """TC-TI009-021"""

    def test_bilibili_registered_correctly(self):
        """TC-TI009-021: bilibili正确注册到DiscussionSourceABC"""
        from steam_publisher_predictor.services.discussion_source_base import (
            _source_registry,
        )
        # BilibiliSource 被装饰器注册
        assert "bilibili" in _source_registry
        assert _source_registry["bilibili"] is bili.BilibiliSource

    def test_source_type_constant(self):
        """TC-TI009-021b: SOURCE_TYPE常量"""
        assert bili.BilibiliSource.SOURCE_TYPE == "bilibili"
