
"""
Metadata-aware re-ranking for semantic search results.

Applies small additive boosts on top of vector similarity so that
more recent and higher-quality documents rank slightly higher when
similarity scores are otherwise close. Boosts are intentionally
small — semantic relevance always dominates.
"""

import os
from datetime import datetime, timezone
from typing import Optional


# Maximum additive boost for recency. Keep well below the
# SIMILARITY_THRESHOLD gap so a recent but weak match can't
# displace a strong one.
_MAX_RECENCY_BOOST: float = float(os.getenv("METADATA_RECENCY_BOOST_MAX", "0.05"))

# Files uploaded within this many days receive the full recency boost.
_FULL_BOOST_DAYS: int = 30

# Files older than this receive zero recency boost.
_ZERO_BOOST_DAYS: int = 365

# Boost awarded to structured/rich file types (PDFs, slide decks).
# Plain text and unknown types receive no boost.
_FILE_TYPE_BOOSTS: dict[str, float] = {
    "pdf": 0.02,
    "pptx": 0.02,
    "ppt": 0.02,
    "docx": 0.01,
    "doc": 0.01,
}


def _recency_boost(created_at: Optional[datetime]) -> float:
    """Return a [0, _MAX_RECENCY_BOOST] additive score for upload recency."""
    if created_at is None:
        return 0.0

    # Normalise to UTC-aware datetime
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    days_old = (datetime.now(timezone.utc) - created_at).days

    if days_old <= _FULL_BOOST_DAYS:
        return _MAX_RECENCY_BOOST

    if days_old >= _ZERO_BOOST_DAYS:
        return 0.0

    # Linear decay between _FULL_BOOST_DAYS and _ZERO_BOOST_DAYS
    decay_range = _ZERO_BOOST_DAYS - _FULL_BOOST_DAYS
    elapsed = days_old - _FULL_BOOST_DAYS
    factor = 1.0 - (elapsed / decay_range)
    return round(_MAX_RECENCY_BOOST * factor, 4)


def _file_type_boost(file_type: Optional[str]) -> float:
    """Return a small additive boost for structured/rich file types."""
    if not file_type:
        return 0.0
    return _FILE_TYPE_BOOSTS.get(file_type.lower(), 0.0)


def rerank_with_metadata(results: list[dict]) -> list[dict]:
    """
    Re-rank search result dicts using recency and file-type boosts.

    Each dict is expected to have:
        similarity  (float)             — cosine similarity score
        file_type   (str | None)        — e.g. "pdf", "docx"
        created_at  (datetime | None)   — raw DB value

    Each dict gains:
        score (float) — similarity + recency_boost + file_type_boost

    Returns a new list sorted descending by score.
    """
    ranked = []
    for result in results:
        recency = _recency_boost(result.get("created_at"))
        ftype = _file_type_boost(result.get("file_type"))
        result["score"] = round((result.get("similarity") or 0.0) + recency + ftype, 4)
        ranked.append(result)

    return sorted(ranked, key=lambda r: r["score"], reverse=True)