"""Redis client and pub/sub helpers for background jobs and subscriptions."""

import json
import logging

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


def get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


def get_redis() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=get_pool())


async def publish(channel: str, data: dict):
    """Publish a message to a Redis pub/sub channel (for GraphQL subscriptions)."""
    r = get_redis()
    try:
        await r.publish(channel, json.dumps(data))
    except Exception as e:
        logger.warning(f"Redis publish failed: {e}")


async def subscribe(channel: str):
    """Subscribe to a Redis pub/sub channel. Yields parsed messages."""
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


async def enqueue_eval(agent_id: str, trace_id: str | None = None):
    """Push an eval job onto the arq queue."""
    r = get_redis()
    job = json.dumps({"function": "run_eval", "agent_id": agent_id, "trace_id": trace_id})
    await r.rpush("arq:queue", job)


async def close():
    global _pool
    if _pool:
        await _pool.disconnect()
        _pool = None
