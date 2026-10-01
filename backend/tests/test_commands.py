import pytest
from unittest.mock import patch, MagicMock
from product.api.app import create_app
from product.api.commands import monday_cli

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    return app

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@patch('product.api.commands.SessionLocal')
@patch('product.api.commands.fetch_live_bundle')
@patch('product.api.commands.stage_items')
@patch('product.api.commands.load_items_bundle')
@patch('os.getenv')
def test_pull_monday_command(mock_getenv, mock_load, mock_stage, mock_fetch, mock_session, runner):
    # Mock Env Var
    mock_getenv.return_value = "12345"

    # Mock DB session
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_conn = mock_db.bind.raw_connection.return_value
    mock_cursor = mock_conn.cursor.return_value

    # Mock Monday fetch
    mock_fetch.return_value = {
        "items": [{"id": "123", "name": "Test Item"}],
        "subitems": []
    }

    # Mock Load return
    mock_load.return_value = {"ins": 1, "upd": 0, "del": 0, "name_upd": 0}

    # Run command
    result = runner.invoke(monday_cli, ['pull', '--board', 'gced_cycle4', '--dry-run'])

    assert result.exit_code == 0
    assert "Starting ingest" in result.output
    assert "Processing board" in result.output
    assert "Dry run: Rolled back changes" in result.output

    # Verify calls
    mock_fetch.assert_called()
    mock_stage.assert_called()
    mock_load.assert_called()
