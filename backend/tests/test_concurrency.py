import asyncio
import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.pipeline import build_graph
from tests.conftest import CANONICAL_CORPUS_FILES, cleanup_pile, seed_pile


async def _run_once(pile_id: str, document_ids: list[str]) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver)
        return await graph.ainvoke(
            {"pile_id": pile_id, "run_id": str(uuid.uuid4()), "document_ids": document_ids},
            config=config,
        )


@pytest.mark.asyncio
async def test_two_piles_run_concurrently_without_cross_contamination(tmp_path):
    """Behavior #9: two runs at the same time stay two runs. This covers the
    "two piles" half of that behavior with the real pipeline. The harder
    "same pile hit twice" half needs the deliverable-section upsert to be
    race-safe (a unique constraint + ON CONFLICT/row locking) — that
    hardening is Phase 4 scope per build-plan.md, not yet built, so it isn't
    claimed here.
    """
    pile_id_1, document_ids_1 = seed_pile(tmp_path, CANONICAL_CORPUS_FILES)
    pile_id_2, document_ids_2 = seed_pile(tmp_path, CANONICAL_CORPUS_FILES)

    try:
        result_1, result_2 = await asyncio.gather(
            _run_once(pile_id_1, document_ids_1),
            _run_once(pile_id_2, document_ids_2),
        )

        assert result_1["pile_id"] == pile_id_1
        assert result_2["pile_id"] == pile_id_2
        for result in (result_1, result_2):
            assert result["stages_completed"] == [
                "ingest",
                "classify",
                "extract_facts",
                "detect_conflicts",
                "draft_deliverable",
            ]
            assert len(result["conflicts"]) > 0
        # Same corpus in both piles, run independently — same conflict types found in each,
        # not merged or dropped between the two concurrent runs.
        assert {c["conflict_type"] for c in result_1["conflicts"]} == {
            c["conflict_type"] for c in result_2["conflicts"]
        }
    finally:
        cleanup_pile(pile_id_1)
        cleanup_pile(pile_id_2)
