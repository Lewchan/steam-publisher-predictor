"""Tests for the discussion-source adapter abstraction."""

from __future__ import annotations

import pytest

from steam_publisher_predictor.services.discussion_source_base import (
    DiscussionSourceABC,
    NormalizedDiscussionResult,
    list_registered_sources,
    register_discussion_source,
)


class DummySource(DiscussionSourceABC):
    """Concrete implementation for testing the registry."""

    SOURCE_TYPE: str = "dummy"

    def fetch(self, game_name: str, max_results: int = 20) -> NormalizedDiscussionResult:
        return NormalizedDiscussionResult(
            source_type=self.SOURCE_TYPE,
            game_name=game_name,
            post_count=5,
        )


class TestNormalizedDiscussionResult:
    def test_is_valid_when_no_error(self):
        r = NormalizedDiscussionResult(source_type="x", game_name="test")
        assert r.is_valid is True

    def test_is_invalid_when_error_set(self):
        r = NormalizedDiscussionResult(
            source_type="x",
            game_name="test",
            error_message="network down",
        )
        assert r.is_valid is False


class TestRegistration:
    """Test the discussion-source registry."""

    def test_register_and_lookup(self):
        # Register the dummy source
        register_discussion_source("dummy_test")(DummySource)
        assert "dummy_test" in list_registered_sources()

    def test_list_registered_sources_sorted(self):
        sources = list_registered_sources()
        assert sources == sorted(sources)

    def test_abc_not_instantiable(self):
        with pytest.raises(TypeError):
            DiscussionSourceABC()  # type: ignore[abstract]
