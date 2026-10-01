"""
Tests for _map_pjt_it() mapper in product/db/core_mapping.py.

The function uses raw psycopg SQL, so tests mock the connection/cursor
and verify the correct SQL is executed for each mapping step.

psycopg is stubbed at import time so these tests run without the Docker
DB environment (matching the pattern needed for local pytest runs).
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch


BOARD_ID = "10000000002"
INCUBATION_BOARD_ID = "1000000001"


# ---------------------------------------------------------------------------
# Stub heavy dependencies before importing core_mapping.
# This lets the tests run on Python 3.9 (dev/CI without Docker).
# ---------------------------------------------------------------------------
def _stub_modules():
    # psycopg
    psycopg_mod = types.ModuleType("psycopg")
    psycopg_mod.Connection = object
    sys.modules.setdefault("psycopg", psycopg_mod)

    # monday_pull (used by clients.py)
    mp_mod = types.ModuleType("monday_pull")
    mp_core = types.ModuleType("monday_pull.core")
    mp_engine = types.ModuleType("monday_pull.core.engine")
    mp_engine.pull_board = MagicMock(return_value={})
    sys.modules.setdefault("monday_pull", mp_mod)
    sys.modules.setdefault("monday_pull.core", mp_core)
    sys.modules.setdefault("monday_pull.core.engine", mp_engine)

    # monday_ingest.clients — stub get_precap_board_ids so core_mapping can import
    mi_mod = types.ModuleType("monday_ingest")
    mi_clients = types.ModuleType("monday_ingest.clients")
    mi_clients.get_precap_board_ids = MagicMock(return_value=set())
    sys.modules.setdefault("monday_ingest", mi_mod)
    sys.modules.setdefault("monday_ingest.clients", mi_clients)


_stub_modules()


# ---------------------------------------------------------------------------
# Import module under test (after stubs are in place)
# ---------------------------------------------------------------------------
from product.db import core_mapping  # noqa: E402
from product.db.core_mapping import _map_pjt_it, _upsert_projects_people_raw, map_monday_to_core  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_conn(with_project_rows: bool = True):
    """Return (mock_conn, mock_cursor) wired up as a context-manager cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (3,)
    if with_project_rows:
        cursor.fetchall.side_effect = [
            [(111, "Project Alpha")],
            [("proj-uuid-1", "111")],
            [],
        ]
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def _all_sql(cursor):
    return " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_map_pjt_it_runs_without_error():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    conn.commit.assert_called_once()


def test_map_pjt_it_upserts_projects_with_board_id():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)

    all_sql = _all_sql(cursor)
    assert "INSERT INTO master_dashboard.projects" in all_sql

    create_call = next(
        c for c in cursor.execute.call_args_list
        if "INSERT INTO master_dashboard.projects" in str(c.args[0])
    )
    params = create_call.args[1]
    assert BOARD_ID in params


@pytest.mark.parametrize("stage_fragment,expected_category", [
    ("archive", "Archived"),
    ("hold",    "On Hold"),
    ("closed",  "Archived"),
    ("done",    "Archived"),
    ("complete", "Archived"),
])
def test_status_category_sql_contains_case(stage_fragment, expected_category):
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    sql = _all_sql(cursor).lower()
    assert stage_fragment in sql
    assert expected_category.lower() in sql


def test_map_pjt_it_maps_all_expected_fields():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    sql = _all_sql(cursor)

    for field in (
        "project_code",
        "Item ID",
        "source_board",
        "source_item_id",
        "stage_name",
        "atlas_project_stage",
        "Project Stage (2026)",
        "project_stage",
        "Project Stage (pre 2026)",
        "project_status",
        "status_category",
        "description",
        "cycle_name",
        "links",
        "report_out_deadline",
        "owner_id",
        "tech_lead",
        "team",
        "notify",
        "vertical_id",
        "location_id",
        "idea_proposal_status",
        "poc_proposal_status",
        "poc_results_status",
        "poc_status",
        "cmbu_proposal_status",
        "seed_results_status",
        "project_partner_startups",
        "project_owners",
    ):
        assert field in sql, f"Expected '{field}' in executed SQL"


def test_map_pjt_it_upserts_by_source_identity_and_guards_project_code():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    sql = _all_sql(cursor)

    assert "ON CONFLICT (source_board, source_item_id) DO UPDATE" in sql
    assert "project_code                = EXCLUDED.project_code" in sql
    assert "existing.project_code = p.item_id_code" in sql
    assert "existing.source_board = %s::text" in sql
    assert "p.monday_item_id" in sql
    assert "ON CONFLICT (project_code) DO UPDATE" not in sql


def test_map_pjt_it_people_insert_is_idempotent():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    assert "ON CONFLICT (full_name) DO NOTHING" in _all_sql(cursor)


def test_map_pjt_it_project_owners_upsert_is_idempotent():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    assert "ON CONFLICT (project_id, person_id) DO UPDATE" in _all_sql(cursor)


def test_map_pjt_it_includes_stage_2_partner_startups():
    conn, cursor = _make_conn()
    _map_pjt_it(conn, BOARD_ID)
    sql = _all_sql(cursor)
    assert "board_relation_mkn379fk" in str(cursor.execute.call_args_list)
    assert "project_partner_startups" in sql


def test_upsert_projects_people_raw_uses_source_identity_and_safe_project_code():
    conn, cursor = _make_conn(with_project_rows=False)

    _upsert_projects_people_raw(conn, {BOARD_ID})

    sql = _all_sql(cursor)
    assert "ON CONFLICT (source_board, source_item_id) DO UPDATE" in sql
    assert "existing_same_source.project_code" in sql
    assert "existing_code.project_code = mi.monday_id::text" in sql
    assert "mi.board_id::text || ':' || mi.monday_id::text" in sql
    assert "project_code   = EXCLUDED.project_code" in sql
    assert "ON CONFLICT (project_code) DO UPDATE" not in sql
    assert "p.source_board = mi.board_id::text" in sql


def test_map_monday_to_core_registers_pjt_it(monkeypatch):
    def fake_config_board_ids(*mapper_types):
        return {BOARD_ID} if mapper_types == ("pjt_it",) else set()

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)

    conn, cursor = _make_conn()
    cursor.fetchone.return_value = (0,)

    with patch.object(core_mapping, "_map_pjt_it") as mock_mapper, \
         patch.object(core_mapping, "_map_incubation_projects"), \
         patch.object(core_mapping, "_upsert_projects_people_raw"), \
         patch.object(core_mapping, "_backfill_projects_from_raw"), \
         patch.object(core_mapping, "_backfill_project_source_board"):

        map_monday_to_core(conn, board_ids=[BOARD_ID])

    mock_mapper.assert_called_once_with(conn, BOARD_ID)


def test_map_monday_to_core_scopes_raw_upsert_to_requested_project_board(monkeypatch):
    configured = {
        ("new_venture_proposals",): {"nvp-board"},
        ("contract_status",): {"contract-board"},
        ("korean",): set(),
        ("pjt_it",): {BOARD_ID},
        ("incubation",): {"inc-board"},
        ("incubation_projects",): {INCUBATION_BOARD_ID},
        ("ai_locate_file", "file_metadata"): set(),
    }
    captured = []

    def fake_config_board_ids(*mapper_types):
        return configured.get(tuple(mapper_types), set())

    def fake_upsert(conn, ids):
        captured.append(set(ids))

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)
    monkeypatch.setattr(core_mapping, "_gced_mftf_board_ids", lambda: set())
    monkeypatch.setattr(core_mapping, "_upsert_projects_people_raw", fake_upsert)
    monkeypatch.setattr(core_mapping, "_map_pjt_it", lambda conn, board_id: None)
    monkeypatch.setattr(core_mapping, "_backfill_projects_from_raw", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_backfill_project_source_board", lambda conn: None)

    map_monday_to_core(_make_conn()[0], board_ids=[BOARD_ID])

    assert captured == [{BOARD_ID}]


def test_map_monday_to_core_full_map_uses_all_non_contract_project_sources(monkeypatch):
    configured = {
        ("new_venture_proposals",): {"nvp-board"},
        ("contract_status",): {"contract-board"},
        ("korean",): set(),
        ("pjt_it",): {BOARD_ID},
        ("incubation",): {"inc-board"},
        ("incubation_projects",): {INCUBATION_BOARD_ID},
        ("ai_locate_file", "file_metadata"): set(),
    }
    captured = []

    def fake_config_board_ids(*mapper_types):
        return configured.get(tuple(mapper_types), set())

    def fake_upsert(conn, ids):
        captured.append(set(ids))

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)
    monkeypatch.setattr(core_mapping, "_gced_mftf_board_ids", lambda: set())
    monkeypatch.setattr(core_mapping, "_upsert_projects_people_raw", fake_upsert)
    monkeypatch.setattr(core_mapping, "_map_nvp", lambda conn, board_id: None)
    monkeypatch.setattr(core_mapping, "_map_pjt_it", lambda conn, board_id: None)
    monkeypatch.setattr(core_mapping, "_map_incubation", lambda conn, board_id: None)
    monkeypatch.setattr(core_mapping, "_map_contract_status", lambda conn, board_id: None)
    monkeypatch.setattr(core_mapping, "_backfill_projects_from_raw", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_backfill_project_source_board", lambda conn: None)

    map_monday_to_core(_make_conn()[0])

    assert captured == [{"nvp-board", BOARD_ID, INCUBATION_BOARD_ID, "inc-board"}]


def test_map_monday_to_core_registers_incubation_projects_as_pjt(monkeypatch):
    def fake_config_board_ids(*mapper_types):
        return {INCUBATION_BOARD_ID} if mapper_types == ("incubation_projects",) else set()

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)

    conn, cursor = _make_conn()
    cursor.fetchone.return_value = (0,)

    with patch.object(core_mapping, "_map_pjt_it") as mock_mapper, \
         patch.object(core_mapping, "_map_incubation_projects") as mock_legacy, \
         patch.object(core_mapping, "_upsert_projects_people_raw"), \
         patch.object(core_mapping, "_backfill_projects_from_raw"), \
         patch.object(core_mapping, "_backfill_project_source_board"):

        map_monday_to_core(conn, board_ids=[INCUBATION_BOARD_ID])

    mock_mapper.assert_called_once_with(conn, INCUBATION_BOARD_ID)
    mock_legacy.assert_not_called()


def test_map_monday_to_core_skips_pjt_it_when_env_unset(monkeypatch):
    monkeypatch.setattr(core_mapping, "_config_board_ids", lambda *mapper_types: set())

    conn, cursor = _make_conn()
    cursor.fetchone.return_value = (0,)

    with patch.object(core_mapping, "_map_pjt_it") as mock_mapper, \
         patch.object(core_mapping, "_upsert_projects_people_raw"), \
         patch.object(core_mapping, "_backfill_projects_from_raw"), \
         patch.object(core_mapping, "_backfill_project_source_board"):

        map_monday_to_core(conn, board_ids=[BOARD_ID])

    mock_mapper.assert_not_called()
