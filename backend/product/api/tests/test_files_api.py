import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import app as app_module


AUTH_HEADER = {"Authorization": "Bearer test-token"}


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.execute = MagicMock()

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, row):
        self.cursor_obj = _Cursor(row)

    def cursor(self):
        return self.cursor_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@contextmanager
def _fake_conn(row):
    yield _Conn(row)


@contextmanager
def _client():
    with patch.dict(os.environ, {"INGEST_API_TOKEN": "test-token"}, clear=False):
        app = app_module.create_app()
        app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})
        with app.test_client() as client:
            yield client


def test_file_resource_requires_auth():
    with _client() as client:
        response = client.get("/atlas/files/file-1")

    assert response.status_code == 401


def test_file_resource_returns_presigned_url_for_authorized_request():
    with _client() as client:
        with patch.object(app_module, "get_conn", return_value=_fake_conn(("monday/key.pdf", "Report.pdf"))):
            with patch("files.spaces.presign", return_value="https://signed.example/report.pdf") as presign:
                response = client.get("/atlas/files/file-1?expires=120", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.get_json() == {
        "url": "https://signed.example/report.pdf",
        "file_name": "Report.pdf",
        "key": "monday/key.pdf",
    }
    presign.assert_called_once_with("monday/key.pdf", expires_in=120)


def test_file_resource_returns_404_for_missing_file():
    with _client() as client:
        with patch.object(app_module, "get_conn", return_value=_fake_conn(None)):
            response = client.get("/atlas/files/missing", headers=AUTH_HEADER)

    assert response.status_code == 404
    assert response.get_json() == {"error": "File not found"}
