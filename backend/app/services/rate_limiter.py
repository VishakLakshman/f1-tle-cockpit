"""
Redis sliding window rate limiter.

Uses a sorted set per client IP in Upstash Redis:
  - Key:   ratelimit:{ip}
  - Score: Unix timestamp of each request
  - TTL:   window_seconds (auto-expires old keys)

On each request:
  1. Remove scores older than (now - window)
  2. Count remaining scores
  3. If count >= limit → reject with 429
  4. Otherwise → add current timestamp, set TTL, allow

This approach is accurate across all Lambda instances simultaneously
because state lives in Redis, not in Lambda memory.
"""

import time
from app.services.redis_service import get_client

# 3 requests per 60-second window per IP
RATE_LIMIT   = int(3)
WINDOW_S     = int(120)


def is_rate_limited(client_ip: str) -> tuple[bool, int, int]:
    """
    Returns (is_limited, requests_used, retry_after_seconds).

    is_limited      — True if the client has exceeded the limit
    requests_used   — how many requests in the current window
    retry_after_s   — seconds until the oldest request expires (if limited)
    """
    key = f"ratelimit:{client_ip}"
    now = time.time()
    window_start = now - WINDOW_S

    try:
        client = get_client()
        pipe = client.pipeline()

        # Remove timestamps older than the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count requests in current window
        pipe.zcard(key)
        # Add current request timestamp
        pipe.zadd(key, {str(now): now})
        # Reset TTL on the key
        pipe.expire(key, WINDOW_S)

        results = pipe.execute()
        count_before_add = results[1]   # count BEFORE adding current request

        if count_before_add >= RATE_LIMIT:
            # Find oldest timestamp to compute retry-after
            oldest = client.zrange(key, 0, 0, withscores=True)
            retry_after = 0
            if oldest:
                oldest_ts = oldest[0][1]
                retry_after = max(0, int(WINDOW_S - (now - oldest_ts)) + 1)
            return True, count_before_add, retry_after

        return False, count_before_add + 1, 0

    except Exception as e:
        # If Redis is unavailable, fail open (allow the request)
        # so a Redis outage doesn't take down the API
        print(f"[RateLimit] Redis error — failing open: {e}")
        return False, 0, 0