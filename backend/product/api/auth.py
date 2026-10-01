from __future__ import annotations

import os
import time
import functools
from typing import Any

import jwt
import requests
from flask import request

# ---------------------------------------------------------------------------
# JWKS caching
# ---------------------------------------------------------------------------

_jwks_cache: list[dict[str, Any]] = []
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # seconds


_DEFAULT_JWKS_URL = (
    "https://keycloak.example.com/realms/example-realm/protocol/openid-connect/certs"
)


def get_jwks() -> list[dict[str, Any]]:
    """Return cached JWKS keys, refreshing if stale."""
    global _jwks_cache, _jwks_fetched_at
    if not _jwks_cache or (time.time() - _jwks_fetched_at) > _JWKS_TTL:
        url = os.environ.get("KEYCLOAK_JWKS_URL", _DEFAULT_JWKS_URL)
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        _jwks_cache = resp.json().get("keys", [])
        _jwks_fetched_at = time.time()
    return _jwks_cache


def _get_signing_key(token: str) -> jwt.PyJWK:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key_data in get_jwks():
        if key_data.get("kid") == kid:
            return jwt.PyJWK(key_data)
    raise ValueError(f"No JWKS key found for kid={kid!r}")


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def get_jwt_roles(token: str) -> list[str]:
    """Try to decode a JWT and return its realm roles. Returns [] if not a JWT or if invalid."""
    if token.count(".") != 2:
        return []
    try:
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload.get("realm_access", {}).get("roles", [])
    except Exception:
        return []


def require_role(role: str):
    """Decorator: verifies the Keycloak JWT and checks for a required realm role."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            parts = auth.strip().split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return (
                    {"error": {"type": "auth_error", "message": "Unauthorized"}},
                    401,
                    {"WWW-Authenticate": 'Bearer realm="atlas"'},
                )

            token = parts[1]
            try:
                signing_key = _get_signing_key(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    options={"verify_aud": False},
                )
            except Exception:
                return (
                    {"error": {"type": "auth_error", "message": "Unauthorized"}},
                    401,
                    {"WWW-Authenticate": 'Bearer realm="atlas"'},
                )

            roles: list[str] = payload.get("realm_access", {}).get("roles", [])
            if role not in roles:
                return (
                    {"error": {"type": "auth_error", "message": "Forbidden"}},
                    403,
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator
