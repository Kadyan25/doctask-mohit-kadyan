"""Full MCP tool set — the same operations as the REST API, exposed as tools,
sharing the identical compiled graphs via app.shared_state (set once in
main.py's lifespan) so a program driving this system through MCP and one
driving it through REST can never see divergent state. Approval is exposed
as a callable tool here too — the whole flow, including the human gate, is
drivable end to end without a person clicking through the review UI.
"""

import base64
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer

from app import shared_state
from app.api.review import ReviewDecision, _apply_decision
from app.config import settings
from app.db.models import ChangelogEntry, DeliverableSection, Document, PendingReview, Pile, Rule, Run
from app.db.session import SessionLocal
from app.services.cost_report import build_cost_report
from app.services.document_parser import SUPPORTED_EXTENSIONS

mcp = MCPServer("doctask-mohit-kadyan")


@mcp.tool()
def ping() -> str:
    """Health check — proves the MCP server is reachable."""
    return "pong"


@mcp.tool()
def create_pile(name: str) -> dict:
    """Create a new pile (project) and its watched folder."""
    with SessionLocal() as db:
        pile = Pile(name=name)
        db.add(pile)
        db.commit()
        db.refresh(pile)

        watch_dir = Path(settings.watch_folder_path) / str(pile.id)
        watch_dir.mkdir(parents=True, exist_ok=True)
        pile.watch_folder_path = str(watch_dir)
        db.commit()
        db.refresh(pile)

        return {
            "id": str(pile.id),
            "name": pile.name,
            "watch_folder_path": pile.watch_folder_path,
            "created_at": pile.created_at.isoformat(),
        }


@mcp.tool()
def upload_document(pile_id: str, filename: str, content_base64: str) -> dict:
    """Upload a document to a pile. Content must be base64-encoded (MCP tool
    arguments are text; this is the standard way to carry binary-safe file
    content through one)."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported format {suffix!r} — supported: {', '.join(SUPPORTED_EXTENSIONS)}")

    with SessionLocal() as db:
        pile = db.get(Pile, pile_id)
        if pile is None:
            raise ValueError(f"pile {pile_id} not found")

        content = base64.b64decode(content_base64)
        storage_dir = Path(settings.document_storage_path) / str(pile_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        dest = storage_dir / filename
        dest.write_bytes(content)

        document = Document(
            pile_id=pile_id,
            filename=filename,
            mime_type="application/octet-stream",
            raw_storage_path=str(dest),
            content_hash=hashlib.sha256(content).hexdigest(),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return {"id": str(document.id), "pile_id": str(pile_id), "filename": filename}


@mcp.tool()
def submit_rule(pile_id: str, rule_text: str) -> dict:
    """Add a governance rule to a pile's checklist, checked on the next examine run."""
    with SessionLocal() as db:
        pile = db.get(Pile, pile_id)
        if pile is None:
            raise ValueError(f"pile {pile_id} not found")
        rule = Rule(pile_id=pile_id, rule_text=rule_text, source="mcp")
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return {"id": str(rule.id), "pile_id": str(pile_id), "rule_text": rule_text}


async def _run_graph(pile_id: str, graph, initial_state: dict) -> dict:
    with SessionLocal() as db:
        pile = db.get(Pile, pile_id)
        if pile is None:
            raise ValueError(f"pile {pile_id} not found")
        thread_id = str(uuid.uuid4())
        run = Run(pile_id=pile_id, status="running", thread_id=thread_id)
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = str(run.id)

    config = {"configurable": {"thread_id": thread_id}}
    try:
        await graph.ainvoke({**initial_state, "run_id": run_id}, config=config)
        status = "completed"
    except Exception as exc:
        status = "failed"
        with SessionLocal() as db:
            run_row = db.get(Run, run_id)
            run_row.status = status
            run_row.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise ValueError(f"run failed: {exc}") from exc

    with SessionLocal() as db:
        run_row = db.get(Run, run_id)
        run_row.status = status
        run_row.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run_row)
        return {"id": run_id, "pile_id": str(pile_id), "status": run_row.status}


@mcp.tool()
async def start_run(pile_id: str) -> dict:
    """Movement 1: run the agentic pipeline (ingest, classify, extract facts,
    detect conflicts, draft the register) against every document in the pile."""
    with SessionLocal() as db:
        documents = db.query(Document).filter(Document.pile_id == pile_id).all()
        if not documents:
            raise ValueError("pile has no documents to run against")
        document_ids = [str(d.id) for d in documents]
    return await _run_graph(pile_id, shared_state.graph, {"pile_id": pile_id, "document_ids": document_ids})


@mcp.tool()
async def start_examine(pile_id: str) -> dict:
    """Movement 2: check the pile's already-extracted facts against its rules."""
    return await _run_graph(pile_id, shared_state.examine_graph, {"pile_id": pile_id})


@mcp.tool()
def list_pending_review(pile_id: str) -> list[dict]:
    """List every conflict/finding awaiting human approval or rejection."""
    with SessionLocal() as db:
        items = (
            db.query(PendingReview)
            .filter(PendingReview.pile_id == pile_id)
            .order_by(PendingReview.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(i.id),
                "item_type": i.item_type,
                "payload": i.payload,
                "status": i.status,
                "reviewer": i.reviewer,
            }
            for i in items
        ]


def _decide(item_id: str, status_label: str, reviewer: str) -> dict:
    with SessionLocal() as db:
        try:
            item = _apply_decision(item_id, ReviewDecision(reviewer=reviewer), status_label, db)
        except HTTPException as exc:
            raise ValueError(exc.detail) from exc
        return {"id": str(item.id), "status": item.status, "reviewer": item.reviewer}


@mcp.tool()
def approve_item(item_id: str, reviewer: str = "mcp") -> dict:
    """Approve a pending conflict or finding — the human gate, callable by a program."""
    return _decide(item_id, "approved", reviewer)


@mcp.tool()
def reject_item(item_id: str, reviewer: str = "mcp") -> dict:
    """Reject a pending conflict or finding."""
    return _decide(item_id, "rejected", reviewer)


@mcp.tool()
def get_deliverable(pile_id: str) -> list[dict]:
    """Read the current Project Health Register, section by section."""
    with SessionLocal() as db:
        sections = db.query(DeliverableSection).filter(DeliverableSection.pile_id == pile_id).all()
        return [
            {
                "section_key": s.section_key,
                "content": s.content,
                "version": s.version,
                "citations": s.citations,
            }
            for s in sections
        ]


@mcp.tool()
def get_changelog(pile_id: str) -> list[dict]:
    """What changed, when, because of which source document."""
    with SessionLocal() as db:
        entries = (
            db.query(ChangelogEntry)
            .filter(ChangelogEntry.pile_id == pile_id)
            .order_by(ChangelogEntry.changed_at.desc())
            .all()
        )
        return [
            {
                "section_key": e.section_key,
                "change_summary": e.change_summary,
                "source_document_id": str(e.source_document_id) if e.source_document_id else None,
                "changed_at": e.changed_at.isoformat(),
            }
            for e in entries
        ]


@mcp.tool()
def get_cost_report(run_id: str) -> dict:
    """What a run spent and where the time went, stage by stage."""
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        return build_cost_report(db, run_id)


if __name__ == "__main__":
    mcp.run()
