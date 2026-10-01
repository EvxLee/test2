from flask import request
from flask_limiter import Limiter


def _get_real_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.remote_addr or "")[:45]


limiter = Limiter(key_func=_get_real_ip, default_limits=[])
