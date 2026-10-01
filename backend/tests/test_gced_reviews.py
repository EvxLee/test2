"""
Unit tests for GCED reviews mapping (_map_gced_reviews).

Tests verify that the correct SQL is executed to:
  - insert/upsert reviewer subitems into gced_mftf25_reviews
  - clear stale averaged scores before recomputing
  - recompute startup-level average scores from both score columns
"""
import sys
import types
from unittest.mock import MagicMock, call


def _stub_modules():
    psycopg_mod = types.ModuleType("psycopg")
    psycopg_mod.Connection = object
    sys.modules.setdefault("psycopg", psycopg_mod)

    mi_mod = types.ModuleType("monday_ingest")
    mi_clients = types.ModuleType("monday_ingest.clients")
    mi_clients.get_precap_board_ids = MagicMock(return_value=set())
    sys.modules.setdefault("monday_ingest", mi_mod)
    sys.modules.setdefault("monday_ingest.clients", mi_clients)


_stub_modules()


from product.db.core_mapping import (  # noqa: E402
    _map_gced_reviews,
    _GCED_REVIEW_OVERALL_COL_IDS,
    _GCED_REVIEW_COLLAB_COL_IDS,
)


BOARD_ID = "1234567890"


def _make_conn():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (0,)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def _all_sql(cursor):
    return " ".join(str(call.args[0]) for call in cursor.execute.call_args_list)


def test_review_col_id_constants():
    """Column IDs for the two score fields must match the Monday board schema."""
    assert _GCED_REVIEW_OVERALL_COL_IDS == ["numbers__1"]
    assert _GCED_REVIEW_COLLAB_COL_IDS == ["numbers_1__1"]


def test_map_gced_reviews_creates_temp_table():
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    sql = _all_sql(cursor)
    assert "CREATE TEMP TABLE tmp_gced_reviewer_rows" in sql


def test_map_gced_reviews_upserts_reviews_table():
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    sql = _all_sql(cursor)
    assert "INSERT INTO master_dashboard.gced_mftf25_reviews" in sql
    assert "ON CONFLICT" in sql


def test_map_gced_reviews_clears_stale_scores_before_recompute():
    """Stale averaged scores must be NULLed before recomputing so removed
    reviewer scores do not persist."""
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    sql = _all_sql(cursor)
    assert "overall_startup_strength = NULL" in sql
    assert "collaboration_potential  = NULL" in sql
    assert "average_score            = NULL" in sql


def test_map_gced_reviews_recomputes_both_score_columns():
    """The UPDATE must set avg values for both score columns, not just one."""
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    sql = _all_sql(cursor)
    assert "overall_startup_strength = sub.avg_overall" in sql
    assert "collaboration_potential  = sub.avg_collab" in sql
    assert "average_score            = sub.avg_score" in sql


def test_map_gced_reviews_avg_score_uses_both_score_columns():
    """average_score must be derived from BOTH overall_startup_strength and
    collaboration_potential — not from a single column."""
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    sql = _all_sql(cursor)
    # Both source columns must appear in the aggregation subquery
    assert "AVG(overall_startup_strength)" in sql
    assert "AVG(collaboration_potential)" in sql
    # The denominator must count non-NULL score columns so a startup with only
    # one reviewer score still receives a correct single-column average rather
    # than being divided by 2.
    assert "CASE WHEN AVG(overall_startup_strength) IS NOT NULL THEN 1 ELSE 0 END" in sql
    assert "CASE WHEN AVG(collaboration_potential)  IS NOT NULL THEN 1 ELSE 0 END" in sql


def test_map_gced_reviews_commits():
    conn, cursor = _make_conn()
    _map_gced_reviews(conn, BOARD_ID)

    conn.commit.assert_called_once()
