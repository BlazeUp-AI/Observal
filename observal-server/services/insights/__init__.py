"""Agent Insights — plugin loader.

The insight generation engine lives in the private `observal-insights` package.
When installed, all insight features are available. When absent, endpoints
return 402 and batch jobs are skipped.

Install for development:
    pip install -e /path/to/observal-insights

Install for deployment:
    pip install git+ssh://git@github.com/ShaanNarendran/observal-insights.git@main
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

try:
    import observal_insights  # noqa: F401

    INSIGHTS_AVAILABLE = True
    logger.info("insights_module_loaded", version=observal_insights.__version__)
except ImportError:
    INSIGHTS_AVAILABLE = False
    logger.info("insights_module_not_installed")


def _not_available(*args, **kwargs):
    raise NotImplementedError(
        "Insights module not installed. Install observal-insights package to enable."
    )


async def generate_report_content(*args, **kwargs):
    if not INSIGHTS_AVAILABLE:
        _not_available()
    return await observal_insights.generate_report_content(*args, **kwargs)


def render_report_html(*args, **kwargs):
    if not INSIGHTS_AVAILABLE:
        _not_available()
    return observal_insights.render_report_html(*args, **kwargs)


def configure_insights():
    """Called at app startup to wire up dependencies into the insights package."""
    if not INSIGHTS_AVAILABLE:
        return

    from config import settings
    from database import async_session
    from models.insight_session_facets import InsightSessionFacets
    from models.insight_session_meta import InsightSessionMeta
    from services.clickhouse import _query
    from services.eval.eval_service import call_eval_model

    observal_insights.configure(
        settings=settings,
        query_fn=_query,
        call_model_fn=call_eval_model,
        db_session_factory=async_session,
        meta_model=InsightSessionMeta,
        facets_model=InsightSessionFacets,
    )
    logger.info("insights_module_configured")
