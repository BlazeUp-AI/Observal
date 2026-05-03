"""Insight report generation orchestrator."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from config import settings
from database import async_session
from models.agent import Agent
from models.insight_report import InsightReport, InsightReportStatus
from services.insights.metrics import compute_all_metrics
from services.insights.narrative import generate_narrative

logger = structlog.get_logger(__name__)


async def generate_report(report_id: str) -> None:
    """Generate an insight report: compute metrics, then generate narrative.

    Updates the InsightReport row in Postgres as it progresses.
    """
    async with async_session() as db:
        stmt = select(InsightReport).where(InsightReport.id == report_id)
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            logger.error("insight_report_not_found", report_id=report_id)
            return

        # Mark as running
        report.status = InsightReportStatus.running
        report.started_at = datetime.now(UTC)
        await db.commit()

        try:
            # Load agent name
            agent_stmt = select(Agent).where(Agent.id == report.agent_id)
            agent_result = await db.execute(agent_stmt)
            agent = agent_result.scalar_one_or_none()
            agent_name = agent.name if agent else "Unknown Agent"

            start_str = report.period_start.strftime("%Y-%m-%d %H:%M:%S")
            end_str = report.period_end.strftime("%Y-%m-%d %H:%M:%S")

            # Step 1: Compute deterministic metrics (queries otel_logs by agent name)
            metrics = await compute_all_metrics(agent_name, start_str, end_str)
            report.metrics = metrics

            session_count = int(metrics.get("overview", {}).get("total_sessions", 0))
            report.sessions_analyzed = session_count
            await db.commit()

            # Step 2: Generate LLM narrative (graceful degradation)
            narrative = await generate_narrative(
                agent_name=agent_name,
                metrics=metrics,
                period_start=start_str,
                period_end=end_str,
                session_count=session_count,
            )
            report.narrative = narrative
            report.llm_model_used = getattr(settings, "EVAL_MODEL_NAME", None) if narrative else None

            # Complete
            report.status = InsightReportStatus.completed
            report.completed_at = datetime.now(UTC)
            await db.commit()

            logger.info(
                "insight_report_completed",
                report_id=report_id,
                sessions=session_count,
                has_narrative=narrative is not None,
            )

        except Exception as e:
            report.status = InsightReportStatus.failed
            report.error_message = str(e)
            report.completed_at = datetime.now(UTC)
            await db.commit()
            logger.exception("insight_report_failed", report_id=report_id, error=str(e))
