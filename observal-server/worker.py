"""arq background worker for eval jobs and async tasks."""

import logging

from arq.connections import RedisSettings
from arq.cron import cron

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
        from services.clickhouse import query_traces
        from services.eval_engine import run_eval_on_trace

        if trace_id:
            scores = await run_eval_on_trace(agent_id, trace_id)
            await publish(
                f"eval:{agent_id}",
                {
                    "agent_id": agent_id,
                    "trace_id": trace_id,
                    "scores_written": len(scores),
                },
            )
        else:
            traces = await query_traces("default", agent_id=agent_id, limit=20)
            for t in traces:
                tid = t.get("trace_id", "")
                scores = await run_eval_on_trace(agent_id, tid)
                await publish(
                    f"eval:{agent_id}",
                    {
                        "agent_id": agent_id,
                        "trace_id": tid,
                        "scores_written": len(scores),
                    },
                )
    except Exception as e:
        logger.exception(f"Eval job failed: {e}")


async def sync_component_sources(ctx: dict):
    """Background job: sync component sources that are due for re-sync."""
    from datetime import UTC, datetime

    from sqlalchemy import or_, select

    from database import async_session
    from models.component_source import ComponentSource
    from services.git_mirror_service import sync_source

    async with async_session() as db:
        # Find sources due for sync
        now = datetime.now(UTC)
        stmt = select(ComponentSource).where(
            ComponentSource.auto_sync_interval.isnot(None),
            or_(
                ComponentSource.last_synced_at.is_(None),
                ComponentSource.last_synced_at + ComponentSource.auto_sync_interval < now,
            ),
        )
        result = await db.execute(stmt)
        sources = result.scalars().all()

        for source in sources:
            logger.info("Syncing component source %s (%s)", source.id, source.url)
            source.sync_status = "syncing"
            await db.commit()

            sync_result = sync_source(source.url, source.component_type)

            source.last_synced_at = now
            source.sync_status = "success" if sync_result.success else "failed"
            source.sync_error = sync_result.error if not sync_result.success else None
            await db.commit()
            logger.info(
                "Sync %s: %s (%d components)",
                source.url,
                source.sync_status,
                len(sync_result.components),
            )


async def startup(ctx: dict):
    logger.info("arq worker started")


async def shutdown(ctx: dict):
    logger.info("arq worker shutting down")


class WorkerSettings:
    """arq worker configuration."""

    functions = [run_eval, sync_component_sources]
    cron_jobs = [cron(sync_component_sources, hour={0, 6, 12, 18})]  # Every 6 hours
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    max_jobs = 5
    job_timeout = 300  # 5 min per eval job
