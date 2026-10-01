import boards_registry


def test_build_registry_uses_db_rows(monkeypatch):
    monkeypatch.setattr(
        boards_registry,
        "get_all_boards",
        lambda: [
            {
                "board_key": "contracts",
                "board_id": "board-1",
                "mapper_type": "contract_status",
            }
        ],
    )

    registry = boards_registry._build_registry()

    assert registry["contracts"][1] == "board-1"


def test_build_registry_skips_rows_without_board_id(monkeypatch):
    monkeypatch.setattr(
        boards_registry,
        "get_all_boards",
        lambda: [{"board_key": "contracts", "board_id": None, "mapper_type": "contract_status"}],
    )

    assert boards_registry._build_registry() == {}


def test_build_registry_skips_non_ingest_rows(monkeypatch):
    monkeypatch.setattr(
        boards_registry,
        "get_all_boards",
        lambda: [{"board_key": "display_only", "board_id": "board-1", "mapper_type": None}],
    )

    assert boards_registry._build_registry() == {}


def test_build_registry_falls_back_to_empty_on_db_error(monkeypatch):
    def fail():
        raise RuntimeError("db down")

    monkeypatch.setattr(boards_registry, "get_all_boards", fail)

    assert boards_registry._build_registry() == {}
