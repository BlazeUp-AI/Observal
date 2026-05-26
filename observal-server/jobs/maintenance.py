# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Maintenance background jobs: ClickHouse optimization, component source sync, retention."""

import structlog
from loguru import logger as optic

logger = structlog.get_logger(__name__)


async def sync_component_sources(ctx: dict):
    """Background job: sync component sources that are due for re-sync."""
    optic.debug("job: sync_component_sources")
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


async def maintain_clickhouse(ctx: dict):
    """Periodic ClickHouse maintenance: compact parts to prevent OOM on long-running agents.

    OPTIMIZE TABLE (without FINAL) merges small parts into larger ones.
    This is lightweight and safe to run frequently.  Without it, a
    month-long agent session accumulates thousands of tiny parts that
    bloat memory during merges and FINAL queries.
    """
    optic.debug("job: maintain_clickhouse")
    from services.clickhouse.client import _query

    tables = ["traces", "spans", "scores", "session_events", "session_stats_agg"]
    for table in tables:
        try:
            await _query(f"OPTIMIZE TABLE {table}")
        except Exception as e:
            logger.warning("ClickHouse OPTIMIZE %s failed: %s", table, e)

    # Check part health: warn before things get critical
    try:
        resp = await _query(
            "SELECT table, count() as parts, sum(rows) as total_rows "
            "FROM system.parts WHERE database = currentDatabase() AND active "
            "GROUP BY table FORMAT JSON"
        )
        if resp.status_code == 200:
            for row in resp.json().get("data", []):
                parts = int(row.get("parts", 0))
                if parts > 300:
                    logger.warning(
                        "ClickHouse table %s has %s active parts, merges may be falling behind",
                        row["table"],
                        parts,
                    )
    except Exception as e:
        logger.debug("Part health check failed: %s", e)
