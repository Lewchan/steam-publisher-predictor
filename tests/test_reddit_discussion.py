"""Tests for the Reddit discussion source adapter."""

from __future__ import annotations

import pytest

from steam_publisher_predictor.services.reddit_discussion import (
    _parse_reddit_json,
    _normalise,
)


class TestParseRedditJson:
    def test_parse_empty_response(self):
        data: dict = {"data": {"children": []}}
        result = _parse_reddit_json(data)
        assert result == []

    def test_parse_single_post(self):
        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Balatro is awesome",
                            "score": 42,
                            "num_comments": 10,
                            "ups": 50,
                            "downs": 8,
                            "permalink": "/r/gaming/comments/abc123/",
                            "created_utc": 1700000000.0,
                            "url": "https://old.reddit.com/r/gaming/comments/abc123/",
                            "selftext": "Just bought Balatro and it's addictive",
                            "subreddit_name_prefixed": "r/gaming",
                        }
                    }
                ]
            }
        }
        result = _parse_reddit_json(data)
        assert len(result) == 1
        assert result[0].title == "Balatro is awesome"
        assert result[0].score == 42
        assert result[0].num_comments == 10
        assert result[0].subreddit == "r/gaming"

    def test_skips_posts_without_title(self):
        data = {
            "data": {
                "children": [
                    {"data": {"title": None, "score": 1}},
                    {"data": {"title": "Valid post", "score": 2}},
                ]
            }
        }
        result = _parse_reddit_json(data)
        assert len(result) == 1
        assert result[0].title == "Valid post"


class TestNormalise:
    def test_empty_list_returns_zero_metrics(self):
        result = _normalise([], source_type="reddit", game_name="TestGame")
        assert result.post_count == 0
        assert result.comment_count == 0
        assert result.total_views == 0

    def test_single_post(self):
        from steam_publisher_predictor.services.reddit_discussion import _RawPost

        items = [_RawPost(
            title="Balatro discussion",
            score=100,
            num_comments=20,
            ups=90,
            downs=10,
        )]
        result = _normalise(items, source_type="reddit", game_name="Balatro")
        assert result.post_count == 1
        assert result.comment_count == 20
        assert result.total_views == 120
        assert result.total_engagement == 120
        assert result.has_hot_content is True
        assert 0.0 < result.avg_upvote_ratio <= 1.0

    def test_has_controversial_when_downs_high(self):
        from steam_publisher_predictor.services.reddit_discussion import _RawPost

        items = [_RawPost(
            title="Controversial post",
            score=5,
            num_comments=30,
            ups=5,
            downs=50,
        )]
        result = _normalise(items, source_type="reddit", game_name="TestGame")
        assert result.has_controversial_content is True
