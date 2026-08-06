import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.pipeline import build_graph


@pytest.mark.asyncio
async def test_kill_and_resume():
    """Behavior #2: a run interrupted mid-flight and resumed later continues
    from the last completed node, losing no finished work — exercised against
    a real Postgres-backed checkpointer, not a mock."""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver, interrupt_after_stage_a=True)

        first = await graph.ainvoke({"stages_completed": []}, config=config)
        assert first["stages_completed"] == ["stage_a"]
        assert first["stage"] == "stage_a_complete"

        # Simulates the process being killed here and restarted: a fresh
        # invoke against the same thread_id, no new input, must continue
        # rather than starting over.
        second = await graph.ainvoke(None, config=config)
        assert second["stages_completed"] == ["stage_a", "stage_b"]
        assert second["stage"] == "stage_b_complete"


@pytest.mark.asyncio
async def test_concurrent_runs_stay_isolated():
    """Behavior #9 at the infra level: two runs (distinct thread_ids) sharing
    one checkpointer never see each other's state."""
    config_1 = {"configurable": {"thread_id": str(uuid.uuid4())}}
    config_2 = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver)

        result_1 = await graph.ainvoke({"stages_completed": [], "pile_id": "pile-1"}, config=config_1)
        result_2 = await graph.ainvoke({"stages_completed": [], "pile_id": "pile-2"}, config=config_2)

        assert result_1["pile_id"] == "pile-1"
        assert result_2["pile_id"] == "pile-2"
        assert result_1["stages_completed"] == ["stage_a", "stage_b"]
        assert result_2["stages_completed"] == ["stage_a", "stage_b"]
