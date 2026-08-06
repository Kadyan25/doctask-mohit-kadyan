import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.models import Conflict, Fact
from app.db.session import SessionLocal
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.pipeline import build_graph


@pytest.mark.asyncio
async def test_kill_after_extract_facts_and_resume(seeded_pile):
    """Behavior #2 against the real pipeline, not a placeholder: interrupted
    right after extract_facts, the facts it already wrote to the database
    stay written (no finished work lost), and resuming continues straight
    through conflict detection and the deliverable draft rather than
    re-running ingestion and extraction from scratch."""
    pile_id, document_ids = seeded_pile
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver, interrupt_after=["extract_facts"])

        first = await graph.ainvoke(
            {"pile_id": pile_id, "run_id": str(uuid.uuid4()), "document_ids": document_ids},
            config=config,
        )
        assert first["stages_completed"] == ["ingest", "classify", "extract_facts"]

        with SessionLocal() as db:
            facts_after_interrupt = db.query(Fact).filter(Fact.pile_id == pile_id).count()
            conflicts_after_interrupt = db.query(Conflict).filter(Conflict.pile_id == pile_id).count()
        assert facts_after_interrupt > 0
        assert conflicts_after_interrupt == 0  # detect_conflicts hasn't run yet — proves no work was skipped ahead

        # Simulates the process being killed here and restarted: a fresh
        # invoke against the same thread_id, no new input, must continue.
        second = await graph.ainvoke(None, config=config)
        assert second["stages_completed"] == [
            "ingest",
            "classify",
            "extract_facts",
            "detect_conflicts",
            "draft_deliverable",
        ]
        assert len(second["conflicts"]) > 0

        with SessionLocal() as db:
            facts_after_resume = db.query(Fact).filter(Fact.pile_id == pile_id).count()
        # Resuming re-entered detect_conflicts onward, not extract_facts again —
        # so the fact count from before the interrupt is unchanged, not doubled.
        assert facts_after_resume == facts_after_interrupt
