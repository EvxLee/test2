import board_config_db


def test_get_board_id_db_value_wins_over_env(monkeypatch):
    monkeypatch.setenv("BOARD_ENV", "env-board")
    monkeypatch.setattr(
        board_config_db,
        "fetch_all",
        lambda sql, params=(): [{"monday_board_id": "db-board", "env_var_name": "BOARD_ENV"}],
    )

    assert board_config_db.get_board_id("example") == "db-board"


def test_get_board_id_falls_back_to_env_when_db_id_null(monkeypatch):
    monkeypatch.setenv("BOARD_ENV", "env-board")
    monkeypatch.setattr(
        board_config_db,
        "fetch_all",
        lambda sql, params=(): [{"monday_board_id": None, "env_var_name": "BOARD_ENV"}],
    )

    assert board_config_db.get_board_id("example") == "env-board"


def test_get_all_boards_excludes_inactive_in_query_and_resolves_ids(monkeypatch):
    captured = {}

    def fake_fetch_all(sql, params=()):
        captured["sql"] = sql
        return [
            {
                "board_key": "contracts",
                "label": "Contracts",
                "category": "other",
                "year": None,
                "display_order": 1,
                "is_active": True,
                "monday_board_id": None,
                "env_var_name": "BOARD_ENV",
                "mapper_type": "contract_status",
            }
        ]

    monkeypatch.setenv("BOARD_ENV", "env-board")
    monkeypatch.setattr(board_config_db, "fetch_all", fake_fetch_all)

    boards = board_config_db.get_all_boards()

    assert "WHERE is_active = TRUE" in captured["sql"]
    assert boards[0]["board_id"] == "env-board"
    assert boards[0]["boardId"] == "env-board"


def test_get_board_ids_by_mapper_type_skips_unresolved(monkeypatch):
    monkeypatch.setattr(
        board_config_db,
        "get_all_boards",
        lambda: [
            {"mapper_type": "gced", "board_id": "1", "category": "gced", "board_key": "a"},
            {"mapper_type": "gced", "board_id": None, "category": "gced", "board_key": "b"},
            {"mapper_type": None, "board_id": "2", "category": "other", "board_key": "c"},
        ],
    )

    assert board_config_db.get_board_ids_by_mapper_type("gced") == {"1"}


def test_get_file_board_ids_includes_ai_locate_and_contract_status_2(monkeypatch):
    monkeypatch.setattr(
        board_config_db,
        "get_all_boards",
        lambda: [
            {"mapper_type": "ai_locate_file", "board_id": "file-1", "category": "files", "board_key": "ai_locate_file"},
            {"mapper_type": "contract_status", "board_id": "file-2", "category": "other", "board_key": "contract_status_2"},
            {"mapper_type": "contract_status", "board_id": "contract-1", "category": "other", "board_key": "contracts"},
        ],
    )

    assert board_config_db.get_file_board_ids_from_config() == ["file-1", "file-2"]


def test_upsert_board_config_rejects_missing_required_fields():
    try:
        board_config_db.upsert_board_config({"board_key": "x"})
    except ValueError as e:
        assert "Missing required fields" in str(e)
    else:
        raise AssertionError("Expected ValueError")
