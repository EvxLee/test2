"""
CORS configuration tests for app.py.

Verifies that:
- /cycles/* allows preflight and real requests from permitted origins
- /cycles/* does not set CORS header for disallowed origins
- Existing /atlas/display/* CORS rules are unaffected
"""

import pytest


ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://atlas-develop.example.com",
]

DISALLOWED_ORIGINS = [
    "https://evil.example.com",
    "http://localhost:3000",
    "https://atlas.example.com",
]


@pytest.fixture(scope="module")
def flask_client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestCyclesCors:
    @pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
    def test_preflight_allowed_origin_returns_cors_header(self, flask_client, origin):
        response = flask_client.options(
            "/cycles/gced_cycle7/summary",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") == origin, (
            f"Expected CORS header for allowed origin {origin!r}"
        )

    @pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
    def test_preflight_disallowed_origin_has_no_cors_header(self, flask_client, origin):
        response = flask_client.options(
            "/cycles/gced_cycle7/summary",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None, (
            f"Expected no CORS header for disallowed origin {origin!r}"
        )

    @pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
    def test_get_allowed_origin_returns_cors_header(self, flask_client, origin):
        """Real GET requests (not just preflight) should also carry the header."""
        from unittest.mock import patch
        with patch("cycles.routes.get_startups_for_cycle", return_value=[]):
            response = flask_client.get(
                "/cycles/gced_cycle7/summary",
                headers={"Origin": origin},
            )
        assert response.headers.get("Access-Control-Allow-Origin") == origin


class TestAtlasDisplayCorsUnaffected:
    """Ensure existing /atlas/display/* CORS rules still work after adding /cycles/*."""

    @pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
    def test_atlas_display_preflight_still_allows_permitted_origins(self, flask_client, origin):
        response = flask_client.options(
            "/atlas/display/data",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") == origin

    @pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
    def test_atlas_display_preflight_still_blocks_disallowed_origins(self, flask_client, origin):
        response = flask_client.options(
            "/atlas/display/data",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None
