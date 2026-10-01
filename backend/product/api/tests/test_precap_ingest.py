import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock heavy transitive dependencies not available outside Docker
_mock_modules = {
    "dotenv": MagicMock(),
    "requests": MagicMock(),
    "psycopg": MagicMock(),
    "monday_pull": MagicMock(),
    "monday_pull.core": MagicMock(),
    "monday_pull.core.engine": MagicMock(),
    "monday_pull.core.client": MagicMock(),
    "monday_pull.core.decoders": MagicMock(),
    "monday_pull.core.assets": MagicMock(),
}


@pytest.fixture(autouse=True)
def mock_heavy_deps():
    """Patch unavailable modules so clients.py and core_mapping.py can import."""
    with patch.dict(sys.modules, _mock_modules):
        for mod_name in ("monday_ingest", "monday_ingest.clients",
                         "db", "db.core_mapping"):
            sys.modules.pop(mod_name, None)
        yield


class TestPrecapEnvVarsRegistered:
    """All 14 Pre-CAP env var names are declared in PRECAP_BOARD_ENV_VARS."""

    def test_all_cycles_registered(self):
        from monday_ingest.clients import PRECAP_BOARD_ENV_VARS

        # 2025: cycles 1-7
        for c in range(1, 8):
            assert f"MONDAY_BOARD_PRECAP_2025_CYCLE{c}_ID" in PRECAP_BOARD_ENV_VARS

        # 2026: cycles 1-7
        for c in range(1, 8):
            assert f"MONDAY_BOARD_PRECAP_2026_CYCLE{c}_ID" in PRECAP_BOARD_ENV_VARS

    def test_env_var_naming_convention(self):
        import re
        from monday_ingest.clients import PRECAP_BOARD_ENV_VARS
        pattern = re.compile(r"^MONDAY_BOARD_PRECAP_\d{4}_CYCLE\d+_ID$")
        for var in PRECAP_BOARD_ENV_VARS:
            assert pattern.match(var), f"{var} doesn't match naming convention"


class TestGetPrecapBoardIds:
    """get_precap_board_ids() resolves board_config GCED mapper rows."""

    def test_returns_configured_ids(self):
        from monday_ingest.clients import get_precap_board_ids
        with patch(
            "monday_ingest.clients.get_board_ids_by_mapper_type",
            return_value={"10000000024", "10000000025"},
        ):
            ids = get_precap_board_ids()
        assert "10000000024" in ids
        assert "10000000025" in ids

    def test_uses_gced_mapper_type(self):
        from monday_ingest.clients import get_precap_board_ids
        with patch("monday_ingest.clients.get_board_ids_by_mapper_type", return_value={"10000000024"}) as mock_get:
            ids = get_precap_board_ids()
        mock_get.assert_called_once_with("gced")
        assert "10000000024" in ids

    def test_returns_empty_set_when_no_rows_resolve(self):
        from monday_ingest.clients import get_precap_board_ids
        with patch("monday_ingest.clients.get_board_ids_by_mapper_type", return_value=set()):
            assert len(get_precap_board_ids()) == 0

    def test_returns_set_not_list(self):
        from monday_ingest.clients import get_precap_board_ids
        with patch("monday_ingest.clients.get_board_ids_by_mapper_type", return_value={"10000000026"}):
            assert isinstance(get_precap_board_ids(), set)


class TestPrecapBoardsMergedIntoGcedSet:
    """core_mapping merges Pre-CAP boards into GCED_BOARD_IDS."""

    def test_link_column_title_included(self):
        """_map_gced_mftf25 must match both 'Hubspot Link' and 'Link' for hubspot_link."""
        import inspect
        from db.core_mapping import _map_gced_mftf25
        source = inspect.getsource(_map_gced_mftf25)
        assert "'Hubspot Link', 'Link'" in source or "'Link', 'Hubspot Link'" in source, (
            "hubspot_link extraction should match both 'Hubspot Link' and 'Link' column titles"
        )

    def test_gced_ids_loaded_from_board_config(self):
        """GCED boards are loaded from board_config mapper_type."""
        import inspect
        from db import core_mapping
        source = inspect.getsource(core_mapping.map_monday_to_core)
        assert 'GCED_BOARD_IDS = _config_board_ids("gced")' in source
