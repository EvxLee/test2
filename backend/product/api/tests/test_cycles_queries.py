import pytest
from unittest.mock import patch, MagicMock

from cycles.queries import get_startups_for_cycle


@patch("cycles.queries.get_cycle_board_map")
@patch("cycles.queries.SessionLocal")
def test_get_startups_for_cycle_returns_data(mock_session_cls, mock_cycle_map):
    """Returns a list of startups with name, description, and vertical."""
    mock_cycle_map.return_value = {"gced_cycle4": "board-123"}

    mock_row = MagicMock()
    mock_row.startup_name = "Acme AI"
    mock_row.description = "We build autonomous agents."
    mock_row.vertical = "AI"

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchall.return_value = [mock_row]
    mock_session_cls.return_value = mock_session

    result = get_startups_for_cycle("gced_cycle4")

    assert len(result) == 1
    assert result[0]["company_name"] == "Acme AI"
    assert result[0]["description"] == "We build autonomous agents."
    assert result[0]["vertical"] == "AI"


@patch("cycles.queries.get_cycle_board_map")
@patch("cycles.queries.SessionLocal")
def test_get_startups_for_cycle_empty(mock_session_cls, mock_cycle_map):
    """Returns an empty list when the cycle has no startups."""
    mock_cycle_map.return_value = {"gced_cycle5": "board-123"}

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchall.return_value = []
    mock_session_cls.return_value = mock_session

    result = get_startups_for_cycle("gced_cycle5")

    assert result == []


@patch("cycles.queries.get_cycle_board_map")
@patch("cycles.queries.SessionLocal")
def test_get_startups_for_cycle_missing_description(mock_session_cls, mock_cycle_map):
    """Returns None for description when PitchBook data is not available."""
    mock_cycle_map.return_value = {"gced_cycle4": "board-123"}

    mock_row = MagicMock()
    mock_row.startup_name = "Stealth Startup"
    mock_row.description = None
    mock_row.vertical = "Healthcare"

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.fetchall.return_value = [mock_row]
    mock_session_cls.return_value = mock_session

    result = get_startups_for_cycle("gced_cycle4")

    assert result[0]["description"] is None


def test_get_startups_for_cycle_invalid_id():
    """Raises ValueError for an unrecognized cycle_id."""
    with pytest.raises(ValueError, match="Invalid cycle_id"):
        get_startups_for_cycle("gced_cycle99")


@patch("cycles.queries.get_cycle_board_map", return_value={})
def test_get_startups_for_cycle_missing_board_config(mock_cycle_map):
    """Raises ValueError when no board_config entry resolves the board ID."""
    with pytest.raises(ValueError, match="No active board_config entry"):
        get_startups_for_cycle("gced_cycle4")


# board_id_for_cycle and cycle_id_for_board_id helpers

def test_board_id_for_cycle_returns_value():
    """Returns the board ID for a known cycle from board_config."""
    from cycles.queries import board_id_for_cycle
    with patch("cycles.queries.get_cycle_board_map", return_value={"gced_cycle7": "10000000020"}):
        assert board_id_for_cycle("gced_cycle7") == "10000000020"


def test_board_id_for_cycle_returns_none_for_unknown_cycle():
    """Returns None for a cycle_id not in CYCLE_ENV_VARS."""
    from cycles.queries import board_id_for_cycle
    assert board_id_for_cycle("gced_cycle99") is None


def test_board_id_for_cycle_returns_none_when_env_unset():
    """Returns None when board_config does not resolve a known cycle."""
    from cycles.queries import board_id_for_cycle
    with patch("cycles.queries.get_cycle_board_map", return_value={}):
        assert board_id_for_cycle("gced_cycle1") is None


def test_cycle_id_for_board_id_returns_cycle():
    """Returns the cycle_id for a known board ID."""
    from cycles.queries import cycle_id_for_board_id
    with patch("cycles.queries.get_cycle_board_map", return_value={"gced_cycle7": "10000000020"}):
        assert cycle_id_for_board_id("10000000020") == "gced_cycle7"


def test_cycle_id_for_board_id_returns_none_for_unknown():
    """Returns None when the board ID maps to no known cycle."""
    from cycles.queries import cycle_id_for_board_id
    with patch("cycles.queries.get_cycle_board_map", return_value={}):
        assert cycle_id_for_board_id("99999999") is None
