import sys
import types
from unittest.mock import MagicMock


def _stub_modules():
    psycopg_mod = types.ModuleType("psycopg")
    psycopg_mod.Connection = object
    sys.modules.setdefault("psycopg", psycopg_mod)


_stub_modules()


def _fake_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


def test_map_monday_to_core_registers_mapper_types_from_board_config(monkeypatch):
    from product.db import core_mapping

    configured = {
        ("new_venture_proposals",): {"nvp-board"},
        ("contract_status",): {"contract-board"},
        ("korean",): {"korean-board"},
        ("pjt_it",): {"pjt-board"},
        ("gced",): {"gced-board"},
        ("incubation",): {"inc-board"},
        ("incubation_projects",): {"inc-projects-board"},
        ("ai_locate_file", "file_metadata"): {"file-board"},
    }
    calls = []

    def fake_config_board_ids(*mapper_types):
        return configured.get(tuple(mapper_types), set())

    def recorder(label):
        def _record(conn, board_id):
            calls.append((label, board_id))
        return _record

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)
    monkeypatch.setattr(core_mapping, "_gced_mftf_board_ids", lambda: {"gced-board"})
    monkeypatch.setattr(core_mapping, "_upsert_projects_people_raw", lambda conn, ids: None)
    monkeypatch.setattr(core_mapping, "_backfill_projects_from_raw", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_backfill_project_source_board", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_map_nvp", recorder("nvp"))
    monkeypatch.setattr(core_mapping, "_map_contract_status", recorder("contract"))
    monkeypatch.setattr(core_mapping, "_map_korean", recorder("korean"))
    monkeypatch.setattr(core_mapping, "_map_pjt_it", recorder("pjt"))
    monkeypatch.setattr(core_mapping, "_map_gced_mftf25", recorder("gced"))
    monkeypatch.setattr(core_mapping, "_map_gced_reviews", recorder("reviews"))
    monkeypatch.setattr(core_mapping, "_map_incubation", recorder("inc"))
    monkeypatch.setattr(core_mapping, "_map_incubation_projects", recorder("inc_projects"))
    monkeypatch.setattr(core_mapping, "_map_ai_locate_file", recorder("files"))

    core_mapping.map_monday_to_core(_fake_conn())

    assert ("nvp", "nvp-board") in calls
    assert ("contract", "contract-board") in calls
    assert ("korean", "korean-board") in calls
    assert ("pjt", "pjt-board") in calls
    assert ("pjt", "inc-projects-board") in calls
    assert ("gced", "gced-board") in calls
    assert ("reviews", "gced-board") in calls
    assert ("inc", "inc-board") in calls
    assert ("inc_projects", "inc-projects-board") not in calls
    assert ("files", "file-board") in calls


def test_map_monday_to_core_dedupes_shared_pjt_incubation_board(monkeypatch):
    from product.db import core_mapping

    shared_board = "1000000001"
    configured = {
        ("new_venture_proposals",): set(),
        ("contract_status",): set(),
        ("korean",): set(),
        ("pjt_it",): {shared_board},
        ("gced",): set(),
        ("incubation",): set(),
        ("incubation_projects",): {shared_board},
        ("ai_locate_file", "file_metadata"): set(),
    }
    calls = []

    def fake_config_board_ids(*mapper_types):
        return configured.get(tuple(mapper_types), set())

    def recorder(label):
        def _record(conn, board_id):
            calls.append((label, board_id))
        return _record

    monkeypatch.setattr(core_mapping, "_config_board_ids", fake_config_board_ids)
    monkeypatch.setattr(core_mapping, "_gced_mftf_board_ids", lambda: set())
    monkeypatch.setattr(core_mapping, "_upsert_projects_people_raw", lambda conn, ids: None)
    monkeypatch.setattr(core_mapping, "_backfill_projects_from_raw", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_backfill_project_source_board", lambda conn: None)
    monkeypatch.setattr(core_mapping, "_map_pjt_it", recorder("pjt"))
    monkeypatch.setattr(core_mapping, "_map_incubation_projects", recorder("inc_projects"))

    core_mapping.map_monday_to_core(_fake_conn(), board_ids=[shared_board])

    assert calls.count(("pjt", shared_board)) == 1
    assert ("inc_projects", shared_board) not in calls


def test_gced_mftf_board_ids_include_env_and_exclude_precap(monkeypatch):
    from product.db import core_mapping

    monkeypatch.setenv("MONDAY_BOARD_GCED_MFTF25_CYCLE5_ID", "10000000022")
    monkeypatch.setenv("MONDAY_BOARD_GCED_MFTF26_CYCLE1_ID", "10000000023")
    monkeypatch.setenv("MONDAY_BOARD_PRECAP_2025_CYCLE5_ID", "1000000018")
    monkeypatch.setattr(core_mapping, "get_all_boards", lambda: [
        {
            "board_id": "10000000013",
            "env_var_name": "MONDAY_BOARD_GCED_MFTF25_CYCLE5_ID",
        },
        {
            "board_id": "1000000018",
            "env_var_name": "MONDAY_BOARD_PRECAP_2025_CYCLE5_ID",
        },
    ])

    board_ids = core_mapping._gced_mftf_board_ids()

    assert "10000000022" in board_ids
    assert "10000000023" in board_ids
    assert "10000000013" in board_ids
    assert "1000000018" not in board_ids
