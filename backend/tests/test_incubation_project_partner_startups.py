"""
Tests for Incubation Projects partner-startup mapping.

These tests stay at the raw-SQL unit level by mocking psycopg cursors, which
matches the rest of the mapper tests in this repo.
"""
import sys
import types
from unittest.mock import MagicMock


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
    _INCUBATION_PROJECT_STAGE_COLUMNS,
    _map_incubation_projects,
)


BOARD_ID = "1000000001"


def _make_conn():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (0,)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def _all_sql(cursor):
    return " ".join(str(call.args[0]) for call in cursor.execute.call_args_list)


def test_stage_column_mapping_matches_incubation_projects_board():
    assert _INCUBATION_PROJECT_STAGE_COLUMNS == {
        "Stage 2": {
            "column_id": "board_relation_mkn379fk",
            "column_title": "Stage 2 (Idea) Startups",
        },
        "Stage 3": {
            "column_id": "connect_boards__1",
            "column_title": "Stage 3 (POC) Startups",
        },
        "Stage 4": {
            "column_id": "board_relation_mkm12tn4",
            "column_title": "Stage 4 (Business Plan) Startups",
        },
        "Stage 5": {
            "column_id": "board_relation_mkm1sz",
            "column_title": "Stage 5 (Seed) Startups",
        },
        "Stage 6": {
            "column_id": "board_relation_mkqa4ttv",
            "column_title": "Stage 6 (SpinOff) Startups",
        },
    }


def test_map_incubation_projects_writes_project_partner_startups():
    conn, cursor = _make_conn()
    cursor.fetchall.side_effect = [
        [(111, "Project Alpha")],
        [("proj-uuid-1", "111")],
        [(
            "111",
            "connect_boards__1",
            {
                "parsed": {
                    "linked_items": [
                        {"linked_item_id": "501", "name": "Startup A"},
                        {"linked_item_id": "502", "name": "Startup B"},
                    ],
                    "display_value": "Startup A, Startup B",
                },
                "raw_text": None,
            },
        )],
    ]

    _map_incubation_projects(conn, BOARD_ID)

    sql = _all_sql(cursor)
    assert "master_dashboard.project_partner_startups" in sql
    assert "master_dashboard.incubation_project_partner_startups" not in sql
    assert "DELETE FROM master_dashboard.project_partner_startups" in sql
    assert "INSERT INTO master_dashboard.project_partner_startups" in cursor.executemany.call_args.args[0]

    inserted_rows = cursor.executemany.call_args.args[1]
    assert inserted_rows == [
        ("proj-uuid-1", "Stage 3", "Startup A"),
        ("proj-uuid-1", "Stage 3", "Startup B"),
    ]
