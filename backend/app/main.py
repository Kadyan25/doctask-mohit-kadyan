import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api import piles, review, runs
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.pipeline import build_graph

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based loop; Windows defaults
    # to ProactorEventLoop, which it explicitly rejects. Must be set before
    # uvicorn creates its event loop. No-op on Linux/Docker, which is what
    # this ships on.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        app.state.checkpointer = saver
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="Document Health Register", lifespan=lifespan)

app.include_router(piles.router)
app.include_router(runs.router)
app.include_router(review.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
