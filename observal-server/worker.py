"""arq background worker for eval jobs and async tasks."""

import structlog
from arq.cron import cron

from logging_config import setup_logging
from services.alert_evaluator import evaluate_alerts
from services.redis import parse_redis_settings, publish

setup_logging()
logger = structlog.get_logger(__name__)


async def run_eval(ctx: dict, agent_id: str, trace_id: str | None = None, project_id: str = "default"):
    """Background job: run eval on an agent's traces."""
    logger.info("eval_started", agent_id=agent_id, trace_id=trace_id, project_id=project_id)
    try:
        from services.clickhouse import query_traces
        from services.eval.eval_engine import run_eval_on_trace

        if trace_id:
            scores = await run_eval_on_trace(agent_id, trace_id, project_id=project_id)
            await publish(
                f"eval:{agent_id}",
                {
                    "agent_id": agent_id,
                    "trace_id": trace_id,
                    "scores_written": len(scores),
                },
            )
        else:
            traces = await query_traces(project_id, agent_id=agent_id, limit=20)
            for t in traces:
                tid = t.get("trace_id", "")
                scores = await run_eval_on_trace(agent_id, tid, project_id=project_id)
                await publish(
                    f"eval:{agent_id}",
                    {
                        "agent_id": agent_id,
                        "trace_id": tid,
                        "scores_written": len(scores),
                    },
                )
    except Exception as e:
        logger.exception("eval_failed", error=str(e))


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


async def maintain_clickhouse(ctx: dict):
    """Periodic ClickHouse maintenance: compact parts to prevent OOM on long-running agents.

    OPTIMIZE TABLE (without FINAL) merges small parts into larger ones.
    This is lightweight and safe to run frequently.  Without it, a
    month-long agent session accumulates thousands of tiny parts that
    bloat memory during merges and FINAL queries.
    """
    from services.clickhouse import _query

    tables = ["traces", "spans", "scores", "mcp_tool_calls", "agent_interactions"]
    for table in tables:
        try:
            await _query(f"OPTIMIZE TABLE {table}")
        except Exception as e:
            logger.warning("ClickHouse OPTIMIZE %s failed: %s", table, e)

    # Check part health — warn before things get critical
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
                        "ClickHouse table %s has %s active parts — merges may be falling behind",
                        row["table"],
                        parts,
                    )
    except Exception as e:
        logger.debug("Part health check failed: %s", e)


async def generate_insight_report(ctx: dict, report_id: str):
    """Background job: generate an insight report for an agent."""
    from services.insights import INSIGHTS_AVAILABLE

    if not INSIGHTS_AVAILABLE:
        logger.warning("insight_report_skipped_not_installed", report_id=report_id)
        return

    logger.info("insight_report_started", report_id=report_id)
    try:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from database import async_session
        from models.agent import Agent
        from models.insight_report import InsightReport, InsightReportStatus
        from services.insights import generate_report_content

        async with async_session() as db:
            stmt = select(InsightReport).where(InsightReport.id == report_id)
            result = await db.execute(stmt)
            report = result.scalar_one_or_none()
            if not report:
                logger.error("insight_report_not_found", report_id=report_id)
                return

            report.status = InsightReportStatus.running
            report.started_at = datetime.now(UTC)
            await db.commit()

            # Load agent
            agent_stmt = select(Agent).where(Agent.id == report.agent_id)
            agent_result = await db.execute(agent_stmt)
            agent = agent_result.scalar_one_or_none()
            agent_name = agent.name if agent else "Unknown Agent"

            start_str = report.period_start.strftime("%Y-%m-%d %H:%M:%S")
            end_str = report.period_end.strftime("%Y-%m-%d %H:%M:%S")

            # Load previous report metrics for regression detection
            previous_metrics = None
            if report.previous_report_id:
                prev_stmt = select(InsightReport).where(InsightReport.id == report.previous_report_id)
                prev_result = await db.execute(prev_stmt)
                prev_report = prev_result.scalar_one_or_none()
                if prev_report and prev_report.aggregated_data:
                    previous_metrics = prev_report.aggregated_data

            # Run the pipeline from the private package
            result_data = await generate_report_content(
                agent_name=agent_name,
                agent_id=str(report.agent_id),
                period_start=start_str,
                period_end=end_str,
                previous_metrics=previous_metrics,
                db=db,
            )

            # Persist results
            report.metrics = result_data.get("metrics")
            report.narrative = result_data.get("narrative")
            report.sessions_analyzed = result_data.get("sessions_analyzed", 0)
            report.aggregated_data = result_data.get("metrics")
            report.report_version = 2 if "user_experience" in (result_data.get("narrative") or {}) else 1

            models_used = result_data.get("models_used", [])
            report.llm_model_used = ", ".join(models_used) if models_used else None

            report.status = InsightReportStatus.completed
            report.completed_at = datetime.now(UTC)
            await db.commit()

            logger.info(
                "insight_report_completed",
                report_id=report_id,
                sessions=report.sessions_analyzed,
                version=report.report_version,
            )
    except Exception as e:
        logger.exception("insight_report_job_failed", report_id=report_id, error=str(e))
        try:
            from datetime import UTC, datetime

            from sqlalchemy import select

            from database import async_session
            from models.insight_report import InsightReport, InsightReportStatus

            async with async_session() as db:
                stmt = select(InsightReport).where(InsightReport.id == report_id)
                result = await db.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    report.status = InsightReportStatus.failed
                    report.error_message = str(e)
                    report.completed_at = datetime.now(UTC)
                    await db.commit()
        except Exception:
            pass


async def batch_generate_insights(ctx: dict):
    """Cron job: discover agents needing reports and queue generation."""
    from services.insights import INSIGHTS_AVAILABLE

    if not INSIGHTS_AVAILABLE:
        return

    from services.insights.batch import discover_and_queue_reports

    try:
        queued = await discover_and_queue_reports()
        if queued > 0:
            logger.info("insight_batch_queued_reports", count=queued)
    except Exception as e:
        logger.exception("insight_batch_failed", error=str(e))


async def startup(ctx: dict):
    logger.info("arq worker started")


async def shutdown(ctx: dict):
    logger.info("arq worker shutting down")


class WorkerSettings:
    """arq worker configuration."""

    functions = [run_eval, sync_component_sources, evaluate_alerts, maintain_clickhouse, generate_insight_report, batch_generate_insights]
    cron_jobs = [
        cron(sync_component_sources, hour={0, 6, 12, 18}),  # Every 6 hours
        cron(evaluate_alerts, second={0}, timeout=55),  # Every minute
        cron(maintain_clickhouse, hour={0, 4, 8, 12, 16, 20}, timeout=120),  # Every 4 hours
        cron(batch_generate_insights, weekday={0}, hour={6}, minute={0}, timeout=300),  # Weekly Monday 6AM
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = parse_redis_settings()
    max_jobs = 5
    job_timeout = 600  # 10 min (V2 insights with facet extraction needs more time)
