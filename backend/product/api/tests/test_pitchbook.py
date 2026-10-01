"""
Tests for PitchBook endpoints: auth, SQL safety, mapping, and ingest behavior.

Covers the revisions required by management:
  1. Auth enforcement on /atlas/pitchbook/companies and /atlas/pitchbook/ingest
  2. SQL identifier quoting in the ingest UPSERT
  3. Dead code removal (COMPANY_HEADER_MAP alias)
  4. Mapping and ingest correctness
"""

import io
import os
import pytest
from unittest.mock import patch, MagicMock

AUTH_HEADER = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    with patch.dict(os.environ, {"INGEST_API_TOKEN": "test-token"}, clear=False):
        from app import create_app
        app = create_app()
        app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _csv_payload(content: bytes, filename: str = "test.csv"):
    return {"file": (io.BytesIO(content), filename)}


# ---------------------------------------------------------------------------
# 1. Auth: /atlas/pitchbook/companies
# ---------------------------------------------------------------------------

class TestPitchbookCompaniesAuth:
    def test_unauthenticated_returns_401(self, client):
        """GET /atlas/pitchbook/companies without auth header returns 401."""
        resp = client.get("/atlas/pitchbook/companies")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """GET /atlas/pitchbook/companies with wrong token returns 401."""
        resp = client.get(
            "/atlas/pitchbook/companies",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    @patch("app.fetch_all", return_value=[])
    def test_valid_token_returns_200(self, mock_fetch, client):
        """GET /atlas/pitchbook/companies with correct token returns 200."""
        resp = client.get(
            "/atlas/pitchbook/companies",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. Auth: /atlas/pitchbook/ingest
# ---------------------------------------------------------------------------

class TestPitchbookIngestAuth:
    def test_unauthenticated_returns_401(self, client):
        """POST /atlas/pitchbook/ingest without auth header returns 401."""
        resp = client.post("/atlas/pitchbook/ingest")
        assert resp.status_code == 401

    @patch("app.get_conn")
    def test_valid_token_with_file_accepted(self, mock_conn, client):
        """POST /atlas/pitchbook/ingest with valid token proceeds past auth."""
        csv = b"Company ID,Company Name\nPB123,Acme Corp\n"
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_connection.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_connection.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_conn.return_value = mock_connection

        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
            data=_csv_payload(csv),
            content_type="multipart/form-data",
        )
        # Should get past auth — either 200 or 500 (mock DB), not 401
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# 3. SQL safety: quoted identifiers
# ---------------------------------------------------------------------------

class TestSQLSafety:
    @patch("app.get_conn")
    def test_ingest_sql_uses_quoted_identifiers(self, mock_conn, client):
        """Verify the UPSERT SQL uses quote_ident-style quoting on columns."""
        executed_sqls = []

        mock_cursor = MagicMock()

        def capture_execute(sql, params=None):
            executed_sqls.append(sql)

        mock_cursor.execute = capture_execute

        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_connection.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_connection.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_conn.return_value = mock_connection

        csv = b"Company ID,Company Name,Website\nPB123,Acme Corp,acme.com\n"
        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
            data=_csv_payload(csv),
            content_type="multipart/form-data",
        )

        # Find the INSERT statement
        insert_sqls = [s for s in executed_sqls if "INSERT INTO" in s]
        assert len(insert_sqls) == 1, f"Expected 1 INSERT, got {len(insert_sqls)}"

        sql = insert_sqls[0]
        # Columns should be double-quoted
        assert '"company_id"' in sql
        assert '"company_name"' in sql
        assert '"website"' in sql
        # Table should be quoted
        assert '"dp"."pitchbook_companies"' in sql
        # Conflict column should be quoted
        assert 'ON CONFLICT ("company_id")' in sql

    def test_ingest_rejects_unmapped_columns(self, client):
        """If a column somehow survives that isn't in the allowlist, reject it."""
        # This CSV has a column "Evil Column" that isn't in HEADER_MAP_COMPANY
        # It should be dropped during the "keep only mapped columns" step,
        # so it never reaches the allowlist check. Verify no error, column ignored.
        csv = b"Company ID,Company Name,Evil Column\nPB123,Acme Corp,malicious\n"

        with patch("app.get_conn") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.__enter__ = MagicMock(return_value=mock_connection)
            mock_connection.__exit__ = MagicMock(return_value=False)
            mock_connection.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_connection.cursor.return_value.__exit__ = MagicMock(
                return_value=False
            )
            mock_conn.return_value = mock_connection

            resp = client.post(
                "/atlas/pitchbook/ingest",
                headers=AUTH_HEADER,
                data=_csv_payload(csv),
                content_type="multipart/form-data",
            )

            # Should succeed — unknown column silently dropped
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["rows_upserted"] == 1


# ---------------------------------------------------------------------------
# 4. Mapping correctness
# ---------------------------------------------------------------------------

class TestMappingCorrectness:
    def test_header_map_company_variants_resolve(self):
        """All known header variants map to expected DB column names."""
        from db.pitchbook_mapping import HEADER_MAP_COMPANY

        # Website variants
        assert HEADER_MAP_COMPANY["Website"] == "website"
        assert HEADER_MAP_COMPANY["Company Website"] == "website"

        # City variants
        assert HEADER_MAP_COMPANY["HQ City"] == "hq_city"
        assert HEADER_MAP_COMPANY["Company City"] == "hq_city"

        # Employee variants
        assert HEADER_MAP_COMPANY["Current Employees"] == "employees"
        assert HEADER_MAP_COMPANY["Employees"] == "employees"

        # Country variants
        assert HEADER_MAP_COMPANY["Company Country/Territory/Region"] == "hq_country_region"
        assert HEADER_MAP_COMPANY["HQ Country/Territory/Region"] == "hq_country_region"
        assert HEADER_MAP_COMPANY["HQ Country / Territory / Region"] == "hq_country_region"

    def test_company_profile_detection(self, client):
        """A CSV with 'Company ID' column is detected as company_profile format."""
        csv = b"Company ID,Company Name\nPB123,Acme\n"
        with patch("app.get_conn") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.__enter__ = MagicMock(return_value=mock_connection)
            mock_connection.__exit__ = MagicMock(return_value=False)
            mock_connection.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_connection.cursor.return_value.__exit__ = MagicMock(
                return_value=False
            )
            mock_conn.return_value = mock_connection

            resp = client.post(
                "/atlas/pitchbook/ingest",
                headers=AUTH_HEADER,
                data=_csv_payload(csv),
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200

            # Verify it targeted pitchbook_companies, not pitchbook_deals
            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "pitchbook_companies" in executed_sql

    def test_deal_detection(self, client):
        """A CSV with 'Deal ID' column is detected as deal format."""
        csv = b"Deal ID,Companies\nD123,Acme\n"
        with patch("app.get_conn") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.__enter__ = MagicMock(return_value=mock_connection)
            mock_connection.__exit__ = MagicMock(return_value=False)
            mock_connection.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_connection.cursor.return_value.__exit__ = MagicMock(
                return_value=False
            )
            mock_conn.return_value = mock_connection

            resp = client.post(
                "/atlas/pitchbook/ingest",
                headers=AUTH_HEADER,
                data=_csv_payload(csv),
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200

            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "pitchbook_deals" in executed_sql

    def test_missing_id_column_returns_400(self, client):
        """A CSV with neither Deal ID nor Company ID returns 400."""
        csv = b"Name,Website\nAcme,acme.com\n"
        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
            data=_csv_payload(csv),
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 5. Ingest behavior
# ---------------------------------------------------------------------------

class TestIngestBehavior:
    def test_empty_file_returns_400(self, client):
        """An empty CSV returns 400."""
        csv = b""
        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
            data=_csv_payload(csv),
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_no_file_returns_400(self, client):
        """POST without a file returns 400."""
        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    @patch("app.get_conn")
    def test_footer_rows_filtered(self, mock_conn, client):
        """Rows starting with PitchBook copyright notice are filtered out."""
        upserted_records = []

        mock_cursor = MagicMock()

        def capture_execute(sql, params=None):
            upserted_records.append(params)

        mock_cursor.execute = capture_execute

        mock_connection = MagicMock()
        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_connection.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_connection.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_conn.return_value = mock_connection

        csv = (
            b"Company ID,Company Name\n"
            b"PB123,Acme Corp\n"
            b"\xc2\xa9 PitchBook Data Inc.,\n"  # copyright footer row
        )
        resp = client.post(
            "/atlas/pitchbook/ingest",
            headers=AUTH_HEADER,
            data=_csv_payload(csv),
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Only 1 row should be upserted (footer filtered out)
        assert data["rows_upserted"] == 1


# ---------------------------------------------------------------------------
# 6. Dead code removal regression
# ---------------------------------------------------------------------------

class TestDeadCodeRemoval:
    def test_header_map_company_importable(self):
        """HEADER_MAP_COMPANY is still importable after alias removal."""
        from db.pitchbook_mapping import HEADER_MAP_COMPANY
        assert isinstance(HEADER_MAP_COMPANY, dict)
        assert len(HEADER_MAP_COMPANY) > 0
        assert "Company ID" in HEADER_MAP_COMPANY

    def test_company_header_map_alias_removed(self):
        """The COMPANY_HEADER_MAP alias no longer exists."""
        from db import pitchbook_mapping
        assert not hasattr(pitchbook_mapping, "COMPANY_HEADER_MAP")
