import sys
import pytest
from unittest.mock import MagicMock


def _stub_db_modules():
    """Stub database modules that call create_engine at import time.

    Using MagicMock() as the module object means any attribute access
    (e.g. `from database.models import AnyModel`) resolves to a MagicMock
    without needing to enumerate every model name.
    """
    sys.modules.setdefault("database", MagicMock())
    sys.modules.setdefault("database.db", MagicMock())
    sys.modules.setdefault("database.models", MagicMock())


_stub_db_modules()


@pytest.fixture
def client():
    from app import create_app
    app = create_app()
    app.testing = True
    return app.test_client()
