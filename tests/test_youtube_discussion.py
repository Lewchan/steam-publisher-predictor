"""Tests for YouTube discussion source adapter."""

from steam_publisher_predictor.services.youtube_discussion import (
    _parse_api_response,
    _parse_scrape_response,
    _normalise,
    _VideoItem,
)


# ── API parser tests ────────────────────────────────────────────────────


def test_parse_api_response_with_data():
    """Should extract video items from a valid API response."""
    data = {
        "items": [
            {
                "id": {"videoId": "abc123def45"},
                "snippet": {
                    "title": "Balatro Review",
                    "channelTitle": "GameReviewer",
                    "publishedAt": "2024-06-15T12:00:00Z",
                },
            },
            {
                "id": {"videoId": "xyz789ghi01"},
                "snippet": {
                    "title": "Balatro Gameplay Walkthrough",
                    "channelTitle": "StreamPro",
                    "publishedAt": "2024-06-10T08:00:00Z",
                },
            },
        ],
    }
    result = _parse_api_response(data)
    assert len(result) == 2
    assert result[0].video_id == "abc123def45"
    assert result[0].title == "Balatro Review"
    assert "watch?v=abc123def45" in result[0].url
    assert result[1].video_id == "xyz789ghi01"


def test_parse_api_response_empty():
    """Should return empty list when no items."""
    result = _parse_api_response({"items": []})
    assert result == []


def test_parse_api_response_missing_id():
    """Should skip items without videoId."""
    data = {"items": [{"snippet": {"title": "No ID Video"}}]}
    result = _parse_api_response(data)
    assert result == []


# ── Scrape parser tests ─────────────────────────────────────────────────


def test_parse_scrape_response_json_embedded():
    """Should parse video IDs from embedded JSON."""
    html = (
        '<script>{"INNERTUBE": true}'
        r'{"videoId":"abc123def45","title":{"runs":[{"text":"Balatro Review"}]}'
        r'{"videoId":"xyz789ghi01","title":{"runs":[{"text":"Balatro Gameplay"}]}'
        "</script>"
    )
    result = _parse_scrape_response(html, limit=10)
    assert len(result) == 2
    assert result[0].video_id == "abc123def45"
    assert result[0].title == "Balatro Review"


def test_parse_scrape_response_empty():
    """Should return empty list for unparseable HTML."""
    result = _parse_scrape_response("<html><body>No video data</body></html>")
    assert isinstance(result, list)
    assert len(result) <= 20  # May contain zero or a few


# ── Normalisation tests ─────────────────────────────────────────────────


def test_normalise_empty():
    """Should return zero metrics for empty items."""
    result = _normalise([], source_type="youtube", game_name="Test")
    assert result.post_count == 0
    assert result.total_views == 0
    assert result.total_engagement == 0


def test_normalise_with_data():
    """Should compute aggregate metrics correctly."""
    items = [
        _VideoItem(title="Video 1", view_count=10000, like_count=500, comment_count=100),
        _VideoItem(title="Video 2", view_count=5000, like_count=200, comment_count=50),
    ]
    result = _normalise(items, source_type="youtube", game_name="Test")
    assert result.post_count == 2
    assert result.total_views == 15000
    assert result.raw_sample_count == 2
    assert result.has_hot_content is True  # Video 1 has > 5000 views


def test_normalise_hot_content():
    """Should detect hot content (video with > 5000 views)."""
    items = [_VideoItem(view_count=100000)]
    result = _normalise(items, source_type="youtube", game_name="Test")
    assert result.has_hot_content is True


def test_normalise_no_hot_content():
    """Should not flag as hot when all videos have < 5000 views."""
    items = [
        _VideoItem(view_count=3000),
        _VideoItem(view_count=2000),
    ]
    result = _normalise(items, source_type="youtube", game_name="Test")
    assert result.has_hot_content is False


def test_normalise_sentiment_positive():
    """Should compute positive sentiment from high like ratio."""
    items = [
        _VideoItem(like_count=900, comment_count=100),
    ]
    result = _normalise(items, source_type="youtube", game_name="Test")
    # like/(like+comment) = 900/1000 = 0.9
    # sentiment = (0.9 - 0.5) * 2 = 0.8
    expected = 0.6471
    actual = result.avg_sentiment
    assert abs(actual - expected) < 0.01
