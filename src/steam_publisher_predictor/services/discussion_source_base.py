"""Abstract base for community discussion data sources.

Every public discussion adapter (Reddit, YouTube, Bilibili, etc.) must
implement the :class:`DiscussionSourceABC` interface and return
:py:class:`NormalizedDiscussionResult` — keeping source-specific parsing
isolated and the rest of the pipeline source-agnostic.

See Iteration_Development_Spec.md §15 (Data Adapter Rules).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


# ── Normalised output ─────────────────────────────────────────────────────

@dataclass(slots=True)
class NormalizedDiscussionResult:
    """Project-level normalised discussion data from a single source.

    All downstream consumers (quality scoring, UI, benchmarking) use this
    record regardless of the underlying source.
    """

    source_type: str  # "reddit", "youtube", "bilibili", etc.
    game_name: str
    post_count: int = 0
    comment_count: int = 0
    avg_upvote_ratio: float = 0.0  # 0.0–1.0
    avg_sentiment: float = 0.0  # -1.0 to 1.0
    total_views: int = 0
    total_engagement: int = 0
    has_hot_content: bool = False
    has_controversial_content: bool = False
    fetch_time: str = ""
    raw_sample_count: int = 0
    error_message: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.error_message) is False


# ── Abstract base ─────────────────────────────────────────────────────────

class DiscussionSourceABC(ABC):
    """Abstract base class for discussion data source adapters.

    Rules (Iteration_Development_Spec §15):
    1. Isolate source-specific parsing
    2. Return :py:class:`NormalizedDiscussionResult` (normalized fields)
    3. Preserve raw source values in the sample list
    4. Fail gracefully — never raise on network issues
    5. Do not crash the calculator when a single source is missing
    """

    SOURCE_TYPE: ClassVar[str] = "unknown"

    @abstractmethod
    def fetch(
        self,
        game_name: str,
        max_results: int = 20,
    ) -> NormalizedDiscussionResult:
        """Fetch and normalize discussion data for *game_name*.

        Parameters
        ----------
        game_name:
            Game title to search for across the source.
        max_results:
            Maximum number of raw items to return before normalisation.

        Returns
        -------
        NormalizedDiscussionResult
            Always returns a (possibly empty) normalised result.
            On failure, sets ``error_message`` instead of raising.
        """

    def fetch_batch(
        self,
        game_names: list[str],
        max_results_per_game: int = 20,
    ) -> list[NormalizedDiscussionResult]:
        """Fetch for multiple game names (one result per game).

        Default implementation delegates to :meth:`fetch` in a loop.
        Subclasses may override for batch endpoints.
        """
        return [
            self.fetch(name, max_results=max_results_per_game)
            for name in game_names
        ]


# ── Registry ──────────────────────────────────────────────────────────────

_DISCUSSION_REGISTRY: dict[str, type[DiscussionSourceABC]] = {}


def register_discussion_source(source_type: str):
    """Class-decorator: register a DiscussionSourceABC subclass."""
    def decorator(cls: type[DiscussionSourceABC]) -> type[DiscussionSourceABC]:
        _DISCUSSION_REGISTRY[source_type] = cls
        return cls

    return decorator


def get_discussion_source(source_type: str) -> type[DiscussionSourceABC]:
    """Return the registered class for *source_type*, or None."""
    return _DISCUSSION_REGISTRY.get(source_type)


def list_registered_sources() -> list[str]:
    """Return sorted list of all registered source type keys."""
    return sorted(_DISCUSSION_REGISTRY.keys())
