from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.admin import router as admin_router
from api.routes.agent import router as agent_router
from api.routes.auth import router as auth_router
from api.routes.dashboard import router as dashboard_router
from api.routes.eval import router as eval_router
from api.routes.feedback import router as feedback_router
from api.routes.mcp import router as mcp_router
from api.routes.review import router as review_router
from api.routes.telemetry import router as telemetry_router
from database import engine
from models import Base
from services.clickhouse import init_clickhouse
from services.redis import close as close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_clickhouse()
    yield
    await close_redis()


app = FastAPI(title="Observal", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)
app.include_router(mcp_router)
app.include_router(review_router)
app.include_router(agent_router)
app.include_router(telemetry_router)
app.include_router(dashboard_router)
app.include_router(feedback_router)
app.include_router(eval_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
