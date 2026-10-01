import hashlib
import json
import os
import threading
import time

_DEFAULT_TTL = 3600


class InMemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[object, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl: int = _DEFAULT_TTL):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)


class RedisCache:
    def __init__(self, url: str):
        import pickle
        import redis
        self._client = redis.from_url(url, decode_responses=False)
        self._pickle = pickle

    def get(self, key: str):
        raw = self._client.get(key)
        return self._pickle.loads(raw) if raw is not None else None

    def set(self, key: str, value, ttl: int = _DEFAULT_TTL):
        self._client.setex(key, ttl, self._pickle.dumps(value))


_cache_instance = None


def get_cache():
    global _cache_instance
    if _cache_instance is None:
        url = os.environ.get("REDIS_URL", "").strip()
        _cache_instance = RedisCache(url) if url else InMemoryCache()
    return _cache_instance


def make_cache_key(namespace: str, params: dict) -> str:
    normalized = json.dumps(
        {k: str(v) for k, v in sorted(params.items())},
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{namespace}:{normalized}".encode()).hexdigest()
