import io
import time
import pytest
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import jwt

from app import create_app

# ---------------------------------------------------------------------------
# RSA key pair shared across all tests
# ---------------------------------------------------------------------------

_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537, key_size=2048, backend=default_backend()
)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


def _make_token(roles: list[str] | None = None, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "realm_access": {"roles": roles if roles is not None else ["external-partner"]},
        "iat": now,
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256", headers={"kid": "test-kid"})


def _mock_signing_key() -> MagicMock:
    key = MagicMock()
    key.key = _PUBLIC_KEY
    return key


AUTH_HEADER = {"Authorization": f"Bearer {_make_token()}"}

# Legacy CSV with domain_name column (backward compat)
SIMPLE_CSV = b"domain_name,company\nexample.com,Example Inc\nnew.io,New Co\n"
# PitchBook-format CSV with Website and Companies columns
PITCHBOOK_CSV = (
    b"Companies,Website\nAcme Corp,www.acme.com\nBrand New Co,brandnew.io\n"
)
NO_DOMAIN_CSV = b"company,founded\nExample Inc,2020\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    app = create_app()
    app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _csv_payload(content: bytes, filename: str = "test.csv"):
    return {"file": (io.BytesIO(content), filename)}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_missing_auth_returns_401(client):
    response = client.post("/atlas/partners/check-duplicates")
    assert response.status_code == 401


def test_malformed_token_returns_401(client):
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_wrong_role_returns_403(app, monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    token = _make_token(roles=["some-other-role"])
    with app.test_client() as c:
        response = c.post(
            "/atlas/partners/check-duplicates",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_no_file_returns_400(client):
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
    )
    assert response.status_code == 400


def test_non_csv_file_returns_400(client):
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(b"not a csv", "data.xlsx"),
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_missing_website_column_returns_400(client):
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(NO_DOMAIN_CSV),
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Duplicate detection — website exact match
# ---------------------------------------------------------------------------

@patch("duplicate_check.routes.fetch_all", return_value=[])
@patch("duplicate_check.routes.SessionLocal")
def test_all_unique_returns_correct_flags(mock_session_local, mock_fetch_all, client):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(SIMPLE_CSV),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.content_type.startswith("text/csv")
    body = response.data.decode()
    assert "is_website_duplicate" in body
    assert "True" not in body


@patch("duplicate_check.routes.SessionLocal")
@patch("duplicate_check.routes.fetch_all")
def test_duplicates_are_flagged(mock_fetch_all, mock_session_local, client):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    mock_fetch_all.return_value = [{"website": "example.com"}]

    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(SIMPLE_CSV),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    lines = [line for line in body.strip().split("\n") if line]
    example_row = next(line for line in lines if "example.com" in line)
    assert "True" in example_row
    new_row = next(line for line in lines if "new.io" in line)
    assert "False" in new_row


@patch("duplicate_check.routes.fetch_all", return_value=[])
@patch("duplicate_check.routes.SessionLocal")
def test_blank_domain_not_flagged_as_duplicate(mock_session_local, mock_fetch_all, client):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    csv_with_blank = b"domain_name,company\n,Empty Domain Co\nexample.com,Example\n"
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(csv_with_blank),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    lines = [line for line in body.strip().split("\n") if line]
    blank_row = lines[1]
    assert "False" in blank_row


# ---------------------------------------------------------------------------
# PitchBook CSV format — Website column
# ---------------------------------------------------------------------------

@patch("duplicate_check.routes.fetch_all", return_value=[])
@patch("duplicate_check.routes.SessionLocal")
def test_website_column_accepted(mock_session_local, mock_fetch_all, client):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(PITCHBOOK_CSV),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert "is_website_duplicate" in body


@patch("duplicate_check.routes.SessionLocal")
@patch("duplicate_check.routes.fetch_all")
def test_website_url_normalized_for_matching(mock_fetch_all, mock_session_local, client):
    """https://www.acme.com in CSV matches acme.com in DB."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    mock_fetch_all.return_value = [{"website": "acme.com"}]

    csv = b"Website,Companies\nhttps://www.acme.com,Acme Corp\n"
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(csv),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    lines = [line for line in body.strip().split("\n") if line]
    data_row = lines[1]
    assert "True" in data_row


# ---------------------------------------------------------------------------
# Fuzzy company name matching
# ---------------------------------------------------------------------------

@patch("duplicate_check.routes.SessionLocal")
@patch("duplicate_check.routes.fetch_all")
def test_fuzzy_name_match_flags_duplicate(mock_fetch_all, mock_session_local, client):
    """'Acme Corp' in CSV fuzzy-matches 'Acme Corporation' in DB."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    # No website match, but company name should fuzzy match
    mock_fetch_all.side_effect = [
        [],  # website query returns nothing
        [{"company_name": "Acme Corporation"}],  # company name query
    ]

    csv = b"Website,Companies\nnomatch.io,Acme Corp\n"
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(csv),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert "is_name_duplicate" in body
    lines = [line for line in body.strip().split("\n") if line]
    data_row = lines[1]
    assert "True" in data_row


@patch("duplicate_check.routes.SessionLocal")
@patch("duplicate_check.routes.fetch_all")
def test_distinct_company_name_not_flagged(mock_fetch_all, mock_session_local, client):
    """'Brand New Co' does not fuzzy-match 'Acme Corporation'."""
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session
    mock_fetch_all.side_effect = [
        [],
        [{"company_name": "Acme Corporation"}],
    ]

    csv = b"Website,Companies\nnomatch.io,Brand New Co\n"
    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(csv),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode()
    lines = [line for line in body.strip().split("\n") if line]
    data_row = lines[1]
    # Both website and name should be False
    assert data_row.count("False") == 2


# ---------------------------------------------------------------------------
# before_request: external-partner role restriction
# ---------------------------------------------------------------------------

def test_external_partner_blocked_from_non_partner_route(app, monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    token = _make_token(roles=["external-partner"])
    with app.test_client() as c:
        response = c.get(
            "/atlas/display/startups",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_external_partner_allowed_on_partner_route(app, monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    token = _make_token(roles=["external-partner"])
    with app.test_client() as c:
        # No file sent — expect 400 (not 403), meaning the hook allowed the request through
        response = c.post(
            "/atlas/partners/check-duplicates",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400


def test_non_partner_role_not_blocked(app, monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    token = _make_token(roles=["internal-user"])
    with app.test_client() as c:
        response = c.get(
            "/atlas/display/startups",
            headers={"Authorization": f"Bearer {token}"},
        )
    # Should not be 403 — internal users are not restricted by the hook
    assert response.status_code != 403


def test_static_token_not_blocked_by_hook(app):
    with app.test_client() as c:
        response = c.get(
            "/atlas/display/startups",
            headers={"Authorization": "Bearer not-a-jwt-static-token"},
        )
    # Static token is not a JWT — hook should pass through, not 403
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Rate limit: per-IP via X-Forwarded-For
# ---------------------------------------------------------------------------

@pytest.fixture
def rate_limited_app(monkeypatch):
    monkeypatch.setattr("auth._get_signing_key", lambda _token: _mock_signing_key())
    app = create_app()
    app.config.update({"TESTING": True, "RATELIMIT_ENABLED": True})
    return app


def test_rate_limit_keyed_per_ip(rate_limited_app):
    """Each client IP gets its own rate limit bucket via X-Forwarded-For."""
    with rate_limited_app.test_client() as c:
        # Exhaust the 10/hour limit for IP A
        for _ in range(10):
            c.post(
                "/atlas/partners/check-duplicates",
                headers={"X-Forwarded-For": "10.0.0.1"},
            )

        # 11th request from IP A should be rate limited
        r = c.post(
            "/atlas/partners/check-duplicates",
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert r.status_code == 429

        # First request from IP B should not be rate limited
        r = c.post(
            "/atlas/partners/check-duplicates",
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
        assert r.status_code != 429


@patch("duplicate_check.routes.fetch_all", return_value=[])
@patch("duplicate_check.routes.SessionLocal")
def test_response_includes_original_columns(mock_session_local, mock_fetch_all, client):
    mock_session = MagicMock()
    mock_session_local.return_value = mock_session

    response = client.post(
        "/atlas/partners/check-duplicates",
        headers=AUTH_HEADER,
        data=_csv_payload(SIMPLE_CSV),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    header_line = response.data.decode().split("\n")[0]
    assert "domain_name" in header_line
    assert "company" in header_line
    assert "is_website_duplicate" in header_line
