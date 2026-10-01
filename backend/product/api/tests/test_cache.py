import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cache import InMemoryCache, make_cache_key, get_cache


def test_cache_hit():
    c = InMemoryCache()
    c.set("key1", {"data": 42})
    assert c.get("key1") == {"data": 42}


def test_cache_miss():
    c = InMemoryCache()
    assert c.get("nonexistent") is None


def test_cache_ttl_expiry():
    c = InMemoryCache()
    now = time.time()
    with patch("cache.time") as mock_time:
        mock_time.time.return_value = now
        c.set("key", "value", ttl=10)

        mock_time.time.return_value = now + 11
        assert c.get("key") is None


def test_make_cache_key_stable():
    key1 = make_cache_key("ns", {"b": "2", "a": "1"})
    key2 = make_cache_key("ns", {"a": "1", "b": "2"})
    assert key1 == key2


def test_make_cache_key_namespace_differentiates():
    params = {"query": "test"}
    assert make_cache_key("display", params) != make_cache_key("docsearch", params)


def test_get_cache_returns_inmemory_without_redis_url():
    import cache as cache_module
    cache_module._cache_instance = None
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("REDIS_URL", None)
        instance = cache_module.get_cache()
        assert isinstance(instance, InMemoryCache)
    cache_module._cache_instance = None
