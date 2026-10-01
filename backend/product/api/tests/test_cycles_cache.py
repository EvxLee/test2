import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from cycles.cache import get_cached_summary, write_cached_summary, invalidate_cache, CACHE_TTL_SECONDS


@patch("cycles.cache.SessionLocal")
def test_get_cached_summary_returns_none_when_missing(mock_session_cls):
    """Returns None when no row exists in the cache table."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchone.return_value = None
    mock_session_cls.return_value = mock_session

    assert get_cached_summary("gced_cycle1") is None


@patch("cycles.cache.SessionLocal")
def test_get_cached_summary_returns_payload_when_fresh(mock_session_cls):
    """Returns the cached payload when the row is within TTL."""
    mock_row = MagicMock()
    mock_row.response = {"cycle_id": "gced_cycle1", "summary": "test", "verticals": {}, "total_startups": 0}
    mock_row.generated_at = datetime.now(timezone.utc)

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchone.return_value = mock_row
    mock_session_cls.return_value = mock_session

    result = get_cached_summary("gced_cycle1")
    assert result is not None
    assert result["cycle_id"] == "gced_cycle1"


@patch("cycles.cache.SessionLocal")
def test_get_cached_summary_returns_none_when_stale(mock_session_cls):
    """Returns None when the row is older than the TTL."""
    mock_row = MagicMock()
    mock_row.response = {"summary": "old"}
    mock_row.generated_at = datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_SECONDS + 1)

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchone.return_value = mock_row
    mock_session_cls.return_value = mock_session

    assert get_cached_summary("gced_cycle1") is None


@patch("cycles.cache.SessionLocal")
def test_get_cached_summary_returns_none_on_db_error(mock_session_cls):
    """Swallows SQLAlchemyError and returns None so cache misses never 500 the endpoint."""
    from sqlalchemy.exc import SQLAlchemyError

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.side_effect = SQLAlchemyError("connection failed")
    mock_session_cls.return_value = mock_session

    assert get_cached_summary("gced_cycle1") is None


@patch("cycles.cache.SessionLocal")
def test_write_cached_summary_executes_upsert_and_commits(mock_session_cls):
    """write_cached_summary executes an upsert and commits the session."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session_cls.return_value = mock_session

    payload = {"cycle_id": "gced_cycle1", "summary": "test", "verticals": {}, "total_startups": 5}
    write_cached_summary("gced_cycle1", payload)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("cycles.cache.SessionLocal")
def test_invalidate_cache_executes_delete_and_commits(mock_session_cls):
    """invalidate_cache executes a DELETE and commits the session."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session_cls.return_value = mock_session

    invalidate_cache("gced_cycle1")

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
