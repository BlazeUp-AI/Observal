import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_current_user, get_db
from models.agent import Agent, AgentGoalTemplate
from models.eval import EvalRun, EvalRunStatus, Scorecard
from models.user import User
from schemas.eval import EvalRequest, EvalRunDetailResponse, EvalRunResponse, ScorecardResponse
from services.clickhouse import query_spans
from services.eval_service import evaluate_trace, fetch_traces, parse_scorecard, run_structured_eval
from services.score_aggregator import ScoreAggregator

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])

_scorecard_load = [selectinload(Scorecard.dimensions)]
_eval_run_load = [selectinload(EvalRun.scorecards).selectinload(Scorecard.dimensions)]


@router.post("/agents/{agent_id}", response_model=EvalRunDetailResponse)
async def run_evaluation(
    agent_id: uuid.UUID,
    req: EvalRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Load agent with goal template
    result = await db.execute(
        select(Agent)
        .where(Agent.id == agent_id)
        .options(selectinload(Agent.goal_template).selectinload(AgentGoalTemplate.sections))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create eval run
    eval_run = EvalRun(agent_id=agent.id, triggered_by=current_user.id)
    db.add(eval_run)
    await db.flush()

    trace_id = req.trace_id if req else None
    traces = await fetch_traces(str(agent.id), trace_id=trace_id)

    if not traces:
        eval_run.status = EvalRunStatus.completed
        eval_run.traces_evaluated = 0
        eval_run.completed_at = datetime.now(UTC)
        await db.commit()
        run = await db.execute(select(EvalRun).where(EvalRun.id == eval_run.id).options(*_eval_run_load))
        return EvalRunDetailResponse.model_validate(run.scalar_one())

    try:
        for trace in traces:
            tid = trace.get("event_id", trace.get("trace_id", str(uuid.uuid4())))

            # Try new structured eval first (uses spans from ClickHouse)
            spans = await query_spans("default", tid, limit=500)
            if spans:
                sc = await run_structured_eval(agent, trace, spans, eval_run.id)
            else:
                # Fall back to legacy LLM judge
                judge_result = await evaluate_trace(agent, trace)
                sc = parse_scorecard(judge_result, agent, eval_run.id, tid)

            db.add(sc)
            eval_run.traces_evaluated += 1

        eval_run.status = EvalRunStatus.completed
        eval_run.completed_at = datetime.now(UTC)
    except Exception as e:
        eval_run.status = EvalRunStatus.failed
        eval_run.error_message = str(e)[:2000]
        eval_run.completed_at = datetime.now(UTC)

    await db.commit()
    run = await db.execute(select(EvalRun).where(EvalRun.id == eval_run.id).options(*_eval_run_load))
    return EvalRunDetailResponse.model_validate(run.scalar_one())


@router.get("/agents/{agent_id}/runs", response_model=list[EvalRunResponse])
async def list_eval_runs(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(EvalRun).where(EvalRun.agent_id == agent_id).order_by(EvalRun.started_at.desc()))
    return [EvalRunResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/agents/{agent_id}/scorecards", response_model=list[ScorecardResponse])
async def list_scorecards(
    agent_id: uuid.UUID,
    version: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Scorecard).where(Scorecard.agent_id == agent_id).options(*_scorecard_load)
    if version:
        stmt = stmt.where(Scorecard.version == version)
    result = await db.execute(stmt.order_by(Scorecard.evaluated_at.desc()).limit(50))
    return [ScorecardResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/scorecards/{scorecard_id}", response_model=ScorecardResponse)
async def get_scorecard(
    scorecard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Scorecard).where(Scorecard.id == scorecard_id).options(*_scorecard_load))
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return ScorecardResponse.model_validate(sc)


@router.get("/agents/{agent_id}/compare", response_model=dict)
async def compare_versions(
    agent_id: uuid.UUID,
    version_a: str = Query(...),
    version_b: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare average scores between two agent versions."""
    from sqlalchemy import func

    async def _avg_scores(version: str) -> dict:
        result = await db.execute(
            select(
                func.avg(Scorecard.overall_score).label("avg_overall"),
                func.count(Scorecard.id).label("count"),
            ).where(Scorecard.agent_id == agent_id, Scorecard.version == version)
        )
        row = result.one()
        return {"version": version, "avg_score": round(float(row.avg_overall or 0), 2), "count": row.count}

    return {"version_a": await _avg_scores(version_a), "version_b": await _avg_scores(version_b)}


# ---------------------------------------------------------------------------
# New structured scoring endpoints
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_id}/aggregate", response_model=dict)
async def agent_aggregate(
    agent_id: uuid.UUID,
    window_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate scoring stats for an agent (CI, drift, dimension breakdown)."""
    result = await db.execute(
        select(Scorecard)
        .where(Scorecard.agent_id == agent_id)
        .order_by(Scorecard.evaluated_at.desc())
        .limit(window_size + 50)  # extra for baseline
    )
    scorecards = result.scalars().all()
    sc_dicts = [
        {
            "composite_score": sc.composite_score or (sc.overall_score * 10),
            "dimension_scores": sc.dimension_scores or {},
            "evaluated_at": str(sc.evaluated_at),
        }
        for sc in scorecards
    ]
    aggregator = ScoreAggregator()
    return aggregator.compute_agent_aggregate(sc_dicts, window_size=window_size)


@router.get("/scorecards/{scorecard_id}/penalties", response_model=list[dict])
async def scorecard_penalties(
    scorecard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the list of penalties applied to a scorecard with evidence."""
    result = await db.execute(select(Scorecard).where(Scorecard.id == scorecard_id))
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    # Penalties are stored in raw_output
    raw = sc.raw_output or {}
    return raw.get("penalties", [])
