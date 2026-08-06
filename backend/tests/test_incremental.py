import hashlib
import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.models import ChangelogEntry, Conflict, DeliverableSection, Document
from app.db.session import SessionLocal
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.incremental_pipeline import build_incremental_graph
from app.graph.pipeline import build_graph
from tests.conftest import create_run

EM = chr(0x2014)  # the corpus format's field separator — an actual em dash, not "--"


async def _run_movement1(pile_id: str, document_ids: list[str]) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver)
        return await graph.ainvoke(
            {"pile_id": pile_id, "run_id": create_run(pile_id), "document_ids": document_ids},
            config=config,
        )


async def _run_incremental(pile_id: str, new_document_ids: list[str]) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_incremental_graph(saver)
        return await graph.ainvoke(
            {"pile_id": pile_id, "run_id": create_run(pile_id), "document_ids": new_document_ids},
            config=config,
        )


def _add_document(pile_id: str, tmp_path, filename: str, content: str) -> str:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    with SessionLocal() as db:
        doc = Document(
            pile_id=pile_id,
            filename=filename,
            mime_type="text/markdown",
            raw_storage_path=str(path),
            content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return str(doc.id)


@pytest.mark.asyncio
async def test_untouched_sections_stay_byte_identical(seeded_pile, tmp_path):
    """A new document that only adds an action item must not disturb
    status_summary or milestones — same content_hash, same version, provably
    untouched, not just "probably fine."""
    pile_id, document_ids = seeded_pile
    await _run_movement1(pile_id, document_ids)

    with SessionLocal() as db:
        baseline = {
            s.section_key: (s.content_hash, s.version)
            for s in db.query(DeliverableSection).filter(DeliverableSection.pile_id == pile_id).all()
        }

    new_notes = (
        "Document-Type: meeting_notes\nProject: Atlas Migration\nPeriod: 2026-06-29\n\n"
        f"# Meeting Notes {EM} 2026-06-29\n\nAttendees: Priya\n\nDecisions: None this week.\n\n"
        f"Action-Item: [AI-3] QA Team to prep UAT test plan {EM} Due: 2026-07-05 {EM} Status: open\n"
    )
    new_doc_id = _add_document(pile_id, tmp_path, "meeting_notes_week4.md", new_notes)

    result = await _run_incremental(pile_id, [new_doc_id])
    assert result["stage"] == "changelog_entry_complete"

    with SessionLocal() as db:
        after = {
            s.section_key: (s.content_hash, s.version)
            for s in db.query(DeliverableSection).filter(DeliverableSection.pile_id == pile_id).all()
        }

    assert after["milestones"] == baseline["milestones"]
    assert after["status_summary"] == baseline["status_summary"]
    assert after["action_items"][1] > baseline["action_items"][1]

    with SessionLocal() as db:
        changelog = db.query(ChangelogEntry).filter(ChangelogEntry.pile_id == pile_id).all()
    changed_sections = {c.section_key for c in changelog}
    assert "milestones" not in changed_sections
    assert "status_summary" not in changed_sections
    assert "action_items" in changed_sections


@pytest.mark.asyncio
async def test_new_document_contradicting_register_is_surfaced_not_resolved(seeded_pile, tmp_path):
    """Behavior: when a new source contradicts what the deliverable already
    says, the conflict is surfaced — existing conflicts stay on record, one
    new one is added, nothing gets silently rewritten to agree."""
    pile_id, document_ids = seeded_pile
    result1 = await _run_movement1(pile_id, document_ids)
    baseline_conflict_count = len(result1["conflicts"])

    new_status = (
        "Document-Type: status_report\nProject: Atlas Migration\nPeriod: 2026-06-29\n\n"
        f"# Weekly Status {EM} 2026-06-29\n\nStatus: On Track\nPercent-Complete: 45%\n"
    )
    new_notes = (
        "Document-Type: meeting_notes\nProject: Atlas Migration\nPeriod: 2026-06-29\n\n"
        f"# Meeting Notes {EM} 2026-06-29\n\nAttendees: Priya\n\nDecisions: None this week.\n\n"
        "Blocker: UAT environment not provisioned yet, blocking start of M3.\n"
    )
    status_id = _add_document(pile_id, tmp_path, "status_week4.md", new_status)
    notes_id = _add_document(pile_id, tmp_path, "meeting_notes_week4.md", new_notes)

    result = await _run_incremental(pile_id, [status_id, notes_id])

    new_status_vs_blocker = [
        c
        for c in result["conflicts"]
        if c["conflict_type"] == "status_vs_blocker" and "2026-06-29" in c["description"]
    ]
    assert len(new_status_vs_blocker) == 1

    with SessionLocal() as db:
        all_conflicts = db.query(Conflict).filter(Conflict.pile_id == pile_id).all()
    assert len(all_conflicts) == baseline_conflict_count + 1
