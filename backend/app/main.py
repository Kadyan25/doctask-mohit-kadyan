import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app import shared_state
from app.api import piles, review, runs
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.examine_pipeline import build_examine_graph
from app.graph.incremental_pipeline import build_incremental_graph
from app.graph.pipeline import build_graph
from app.mcp_server import mcp
from app.services.watcher import start_watcher

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
        app.state.examine_graph = build_examine_graph(saver)
        app.state.incremental_graph = build_incremental_graph(saver)

        # Same objects on the shared module, so the MCP server (mounted below,
        # a separate ASGI app) drives the identical graphs the REST routes do.
        shared_state.graph = app.state.graph
        shared_state.examine_graph = app.state.examine_graph
        shared_state.incremental_graph = app.state.incremental_graph

        loop = asyncio.get_event_loop()
        observer = start_watcher(loop, app.state.incremental_graph)
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            observer.stop()
            observer.join()


app = FastAPI(title="Document Health Register", lifespan=lifespan)

app.include_router(piles.router)
app.include_router(runs.router)
app.include_router(review.router)
app.mount("/mcp", mcp.streamable_http_app(streamable_http_path="/"))


@app.get("/health")
async def health():
    return {"status": "ok"}
