import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.models import DeliverableSection, Finding, PendingReview
from app.db.session import SessionLocal
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.examine_pipeline import build_examine_graph
from app.graph.pipeline import build_graph
from tests.conftest import GOVERNANCE_RULES, seed_rules


async def _run_movement1(pile_id: str, document_ids: list[str]) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver)
        return await graph.ainvoke(
            {"pile_id": pile_id, "run_id": str(uuid.uuid4()), "document_ids": document_ids},
            config=config,
        )


async def _run_movement2(pile_id: str) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_examine_graph(saver)
        return await graph.ainvoke({"pile_id": pile_id, "run_id": str(uuid.uuid4())}, config=config)


@pytest.mark.asyncio
async def test_governance_rules_catch_violations_on_the_seeded_corpus(seeded_pile):
    """Movement 2 re-examines facts Movement 1 already extracted (no
    re-parsing) against a natural-language governance checklist, running one
    parallel branch per rule (LangGraph's Send/map-reduce pattern), and finds
    exactly the violations the corpus was seeded with."""
    pile_id, document_ids = seeded_pile
    await _run_movement1(pile_id, document_ids)
    seed_rules(pile_id, GOVERNANCE_RULES)

    result = await _run_movement2(pile_id)

    stages = result["stages_completed"]
    assert "load_rules" in stages
    assert "produce_findings" in stages
    assert len([s for s in stages if s.startswith("check_rule:")]) == 3

    # status-vs-blocker and stale-action-item fire; the scope-change rule
    # correctly stays quiet since change_request_001.md is present.
    assert len(result["findings"]) == 2

    with SessionLocal() as db:
        findings = db.query(Finding).filter(Finding.pile_id == pile_id).all()
        assert len(findings) == 2

        pending = (
            db.query(PendingReview)
            .filter(PendingReview.pile_id == pile_id, PendingReview.item_type == "finding")
            .all()
        )
        assert len(pending) == 2
        assert all(p.status == "pending" for p in pending)

        section = (
            db.query(DeliverableSection)
            .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == "compliance_findings")
            .first()
        )
        assert section is not None
        assert "No findings" not in section.content


@pytest.mark.asyncio
async def test_clean_corpus_produces_honest_no_findings(seeded_clean_pile):
    """Behavior #5: a clean corpus yields an honest, explicit "no findings"
    report — a stated claim that every rule was checked and none were
    violated, not silence and not an empty page."""
    pile_id, document_ids = seeded_clean_pile
    await _run_movement1(pile_id, document_ids)
    seed_rules(pile_id, GOVERNANCE_RULES)

    result = await _run_movement2(pile_id)

    assert result["findings"] == []

    with SessionLocal() as db:
        findings = db.query(Finding).filter(Finding.pile_id == pile_id).all()
        assert len(findings) == 0

        section = (
            db.query(DeliverableSection)
            .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == "compliance_findings")
            .first()
        )
        assert section is not None
        assert "No findings" in section.content
        assert "3 rule(s)" in section.content


@pytest.mark.asyncio
async def test_examine_with_no_rules_is_honest_about_why(seeded_pile):
    """Distinguishes "nothing configured" from "checked and clean" — both are
    zero findings, but the report must say which one actually happened."""
    pile_id, document_ids = seeded_pile
    await _run_movement1(pile_id, document_ids)

    result = await _run_movement2(pile_id)

    assert result["findings"] == []
    with SessionLocal() as db:
        section = (
            db.query(DeliverableSection)
            .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == "compliance_findings")
            .first()
        )
        assert section is not None
        assert "No rules configured" in section.content
