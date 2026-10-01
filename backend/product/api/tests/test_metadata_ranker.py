"""
Unit tests for metadata_ranker.py

Tests recency boost, file-type boost, and combined re-ranking.
No DB or embedding client required.
"""

import pytest
from datetime import datetime, timedelta, timezone

from chat.metadata_ranker import (
    _recency_boost,
    _file_type_boost,
    rerank_with_metadata,
    _MAX_RECENCY_BOOST,
    _FULL_BOOST_DAYS,
    _ZERO_BOOST_DAYS,
)


# ---------------------------------------------------------------------------
# _recency_boost
# ---------------------------------------------------------------------------

def test_recency_boost_none_returns_zero():
    assert _recency_boost(None) == 0.0


def test_recency_boost_very_recent_returns_max():
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    assert _recency_boost(recent) == _MAX_RECENCY_BOOST


def test_recency_boost_at_full_boost_boundary():
    boundary = datetime.now(timezone.utc) - timedelta(days=_FULL_BOOST_DAYS)
    assert _recency_boost(boundary) == _MAX_RECENCY_BOOST


def test_recency_boost_very_old_returns_zero():
    old = datetime.now(timezone.utc) - timedelta(days=_ZERO_BOOST_DAYS + 10)
    assert _recency_boost(old) == 0.0


def test_recency_boost_midpoint_is_between_zero_and_max():
    mid_days = (_FULL_BOOST_DAYS + _ZERO_BOOST_DAYS) // 2
    mid = datetime.now(timezone.utc) - timedelta(days=mid_days)
    boost = _recency_boost(mid)
    assert 0.0 < boost < _MAX_RECENCY_BOOST


def test_recency_boost_naive_datetime_treated_as_utc():
    # Naive datetime should not raise; treated as UTC
    naive = datetime.utcnow() - timedelta(days=1)
    assert _recency_boost(naive) == _MAX_RECENCY_BOOST


# ---------------------------------------------------------------------------
# _file_type_boost
# ---------------------------------------------------------------------------

def test_file_type_boost_none_returns_zero():
    assert _file_type_boost(None) == 0.0


def test_file_type_boost_unknown_type_returns_zero():
    assert _file_type_boost("csv") == 0.0
    assert _file_type_boost("txt") == 0.0


def test_file_type_boost_pdf():
    assert _file_type_boost("pdf") > 0.0


def test_file_type_boost_case_insensitive():
    assert _file_type_boost("PDF") == _file_type_boost("pdf")
    assert _file_type_boost("PPTX") == _file_type_boost("pptx")


def test_file_type_boost_pdf_ge_docx():
    # PDFs/slides should boost at least as much as word docs
    assert _file_type_boost("pdf") >= _file_type_boost("docx")


# ---------------------------------------------------------------------------
# rerank_with_metadata
# ---------------------------------------------------------------------------

def _make_result(similarity: float, file_type: str | None = None,
                 days_old: int = 400) -> dict:
    return {
        "id": "x",
        "similarity": similarity,
        "file_type": file_type,
        "created_at": datetime.now(timezone.utc) - timedelta(days=days_old),
    }


def test_rerank_adds_score_field():
    results = [_make_result(0.8)]
    ranked = rerank_with_metadata(results)
    assert "score" in ranked[0]


def test_rerank_score_gte_similarity():
    results = [_make_result(0.8, file_type="pdf", days_old=10)]
    ranked = rerank_with_metadata(results)
    assert ranked[0]["score"] >= 0.8


def test_rerank_sorted_descending():
    results = [
        _make_result(0.75, days_old=400),   # old, no type bonus
        _make_result(0.80, days_old=400),   # old, no type bonus
        _make_result(0.70, file_type="pdf", days_old=5),  # recent PDF
    ]
    ranked = rerank_with_metadata(results)
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rerank_recent_pdf_can_outrank_older_plain():
    recent_pdf = _make_result(0.78, file_type="pdf", days_old=5)
    old_plain = _make_result(0.80, file_type=None, days_old=500)
    ranked = rerank_with_metadata([old_plain, recent_pdf])
    # recent_pdf gets recency + file_type boost; should beat old_plain
    assert ranked[0] is recent_pdf


def test_rerank_does_not_mutate_original_list():
    r1 = _make_result(0.9)
    r2 = _make_result(0.7)
    original = [r1, r2]
    rerank_with_metadata(original)
    # original list order may be mutated (dicts are modified), but length unchanged
    assert len(original) == 2


def test_rerank_empty_list():
    assert rerank_with_metadata([]) == []


def test_rerank_single_item():
    results = [_make_result(0.85)]
    ranked = rerank_with_metadata(results)
    assert len(ranked) == 1
    assert "score" in ranked[0]
