"""arq background worker for eval jobs and async tasks."""

import json
import logging

from arq import create_pool
from arq.connections import RedisSettings

from config import settings
from services.redis import publish

logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    """Parse REDIS_URL into arq RedisSettings."""
    from urllib.parse import urlparse
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
    )


async def run_eval(ctx: dict, agent_id: str, trace_id: str | None = None):
    """Background job: run eval on an agent's traces."""
    logger.info(f"Running eval for agent={agent_id} trace={trace_id}")
    try:
        from services.eval_service import evaluate_trace, fetch_traces

        traces = await fetch_traces(agent_id, limit=1 if trace_id else 20, trace_id=trace_id)
        for trace in traces:
            result = await evaluate_trace(
                type("Agent", (), {"id": agent_id, "name": "", "prompt": ""})(),
                trace,
            )
            # Publish result for GraphQL subscriptions
            await publish(f"eval:{agent_id}", {
                "agent_id": agent_id,
                "trace_id": trace.get("trace_id", ""),
                "result": result,
            })
    except Exception as e:
        logger.exception(f"Eval job failed: {e}")


async def startup(ctx: dict):
    logger.info("arq worker started")


async def shutdown(ctx: dict):
    logger.info("arq worker shutting down")


class WorkerSettings:
    """arq worker configuration."""
    functions = [run_eval]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    max_jobs = 5
    job_timeout = 300  # 5 min per eval job
