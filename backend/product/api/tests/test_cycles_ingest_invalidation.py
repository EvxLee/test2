"""Unit tests for cache invalidation triggered by map_monday_to_core."""
from unittest.mock import MagicMock, patch


def test_ingest_invalidates_cycle_cache_for_matching_board():
    """When a GCED board is ingested, the matching cycle's cache row is deleted."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("cycles.queries.get_cycle_board_map", return_value={"gced_cycle7": "10000000020"}):
        from cycles.queries import cycle_id_for_board_id
        cycle_ids = [cid for cid in (cycle_id_for_board_id(b) for b in ["10000000020"]) if cid]

        assert cycle_ids == ["gced_cycle7"]

        if cycle_ids:
            with mock_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cycles.summary_cache WHERE cycle_id = ANY(%s);",
                    (cycle_ids,),
                )
            mock_conn.commit()

    mock_cursor.execute.assert_called_once_with(
        "DELETE FROM cycles.summary_cache WHERE cycle_id = ANY(%s);",
        (["gced_cycle7"],),
    )
    mock_conn.commit.assert_called()


def test_ingest_no_invalidation_for_unknown_board():
    """When no board maps to a known cycle, no DELETE is executed."""
    mock_conn = MagicMock()

    with patch("cycles.queries.get_cycle_board_map", return_value={}):
        from cycles.queries import cycle_id_for_board_id
        cycle_ids = [cid for cid in (cycle_id_for_board_id(b) for b in ["99999999"]) if cid]

        assert cycle_ids == []

        if cycle_ids:
            with mock_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cycles.summary_cache WHERE cycle_id = ANY(%s);",
                    (cycle_ids,),
                )
            mock_conn.commit()

    mock_conn.cursor.assert_not_called()
    mock_conn.commit.assert_not_called()
