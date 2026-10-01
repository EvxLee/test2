from types import SimpleNamespace


def _client(monkeypatch, **board_config_patches):
    import board_config_db
    import auth
    from app import create_app

    for name, value in board_config_patches.items():
        monkeypatch.setattr(board_config_db, name, value)

    monkeypatch.setattr(auth, "_get_signing_key", lambda token: SimpleNamespace(key="key"))
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"realm_access": {"roles": ["admin"]}},
    )

    app = create_app()
    app.testing = True
    return app.test_client()


def test_get_boards_config_returns_active_boards(monkeypatch):
    client = _client(
        monkeypatch,
        get_all_boards=lambda: [
            {
                "key": "contracts",
                "label": "Contracts",
                "category": "other",
                "displayOrder": 1,
                "boardId": "board-1",
            }
        ],
    )

    response = client.get("/atlas/boards/config")

    assert response.status_code == 200
    assert response.get_json()["boards"][0]["key"] == "contracts"


def test_post_boards_config_requires_admin(monkeypatch):
    import auth

    client = _client(monkeypatch, upsert_board_config=lambda payload: payload)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"realm_access": {"roles": ["internal-user"]}},
    )

    response = client.post(
        "/atlas/boards/config",
        json={"board_key": "x", "label": "X", "category": "other"},
        headers={"Authorization": "Bearer a.b.c"},
    )

    assert response.status_code == 403


def test_post_boards_config_creates_row_for_admin(monkeypatch):
    client = _client(
        monkeypatch,
        upsert_board_config=lambda payload: {**payload, "boardId": payload.get("monday_board_id")},
    )

    response = client.post(
        "/atlas/boards/config",
        json={"board_key": "x", "label": "X", "category": "other", "monday_board_id": "123"},
        headers={"Authorization": "Bearer a.b.c"},
    )

    assert response.status_code == 201
    assert response.get_json()["board"]["boardId"] == "123"


def test_patch_boards_config_updates_row_for_admin(monkeypatch):
    client = _client(
        monkeypatch,
        update_board_config=lambda board_key, payload: {"key": board_key, **payload},
    )

    response = client.patch(
        "/atlas/boards/config/x",
        json={"is_active": False},
        headers={"Authorization": "Bearer a.b.c"},
    )

    assert response.status_code == 200
    assert response.get_json()["board"]["is_active"] is False
