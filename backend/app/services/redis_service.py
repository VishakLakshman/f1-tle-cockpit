import json
import os
import redis
from typing import Optional, Any


# Upstash Redis uses a REST-compatible URL with TLS
# Set UPSTASH_REDIS_URL=rediss://:password@your-endpoint.upstash.io:6380
_client: Optional[redis.Redis] = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        url = os.getenv("UPSTASH_REDIS_URL")
        if not url:
            raise RuntimeError("UPSTASH_REDIS_URL environment variable not set")
        _client = redis.from_url(url, decode_responses=True)
    return _client


def cache_key(year: int, gp: str, session: str, driver1: str, driver2: str) -> str:
    # Normalise driver order so VER+HAM == HAM+VER
    pair = "_".join(sorted([driver1.upper(), driver2.upper()]))
    return f"ghost:{year}:{gp.replace(' ', '_')}:{session}:{pair}"


def session_key(year: int, gp: str, session: str) -> str:
    return f"session_info:{year}:{gp.replace(' ', '_')}:{session}"


def get_cached(key: str) -> Optional[Any]:
    try:
        client = get_client()
        raw = client.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[Redis] GET error: {e}")
    return None


def set_cached(key: str, value: Any, ttl_seconds: int = 3600 * 24) -> bool:
    """Cache for 24 hours by default — F1 session data never changes."""
    try:
        client = get_client()
        client.setex(key, ttl_seconds, json.dumps(value))
        return True
    except Exception as e:
        print(f"[Redis] SET error: {e}")
        return False