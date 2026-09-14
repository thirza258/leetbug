import hashlib

from fastapi import HTTPException
from redis import Redis, RedisError

from app.config import settings

redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)


def rate_limit(key: str, limit: int, seconds: int = 60):
    if settings.testing:
        return
    bucket = "limit:" + hashlib.sha256(key.encode()).hexdigest()
    try:
        count = redis_client.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1, bucket, seconds,
        )
    except RedisError as exc:
        raise HTTPException(503, "The queue is temporarily unavailable. Please try again shortly.") from exc
    if count > limit:
        raise HTTPException(429, "Too many requests. Please wait a minute before trying again.",
                            headers={"Retry-After": str(seconds)})

