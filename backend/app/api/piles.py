import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChangelogEntryRead,
    DeliverableSectionRead,
    DocumentRead,
    PendingReviewRead,
    PileCreate,
    PileRead,
    RuleCreate,
    RuleRead,
    RunRead,
)
from app.config import settings
from app.db.models import ChangelogEntry, DeliverableSection, Document, PendingReview, Pile, Rule, Run
from app.db.session import get_db
from app.services.document_parser import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/piles", tags=["piles"])


@router.post("", response_model=PileRead)
def create_pile(payload: PileCreate, db: Session = Depends(get_db)) -> Pile:
    pile = Pile(name=payload.name, watch_folder_path=payload.watch_folder_path)
    db.add(pile)
    db.commit()
    db.refresh(pile)
    return pile


@router.get("/{pile_id}", response_model=PileRead)
def get_pile(pile_id: uuid.UUID, db: Session = Depends(get_db)) -> Pile:
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")
    return pile


@router.post("/{pile_id}/documents", response_model=DocumentRead)
async def upload_document(pile_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db)) -> Document:
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported format {suffix!r} — supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    storage_dir = Path(settings.document_storage_path) / str(pile_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    document = Document(
        pile_id=pile_id,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        raw_storage_path=str(dest),
        content_hash=hashlib.sha256(content).hexdigest(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/{pile_id}/rules", response_model=RuleRead)
def submit_rule(pile_id: uuid.UUID, payload: RuleCreate, db: Session = Depends(get_db)) -> Rule:
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")
    rule = Rule(pile_id=pile_id, rule_text=payload.rule_text, source=payload.source)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{pile_id}/rules", response_model=list[RuleRead])
def list_rules(pile_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Rule]:
    return db.query(Rule).filter(Rule.pile_id == pile_id).all()


@router.post("/{pile_id}/runs", response_model=RunRead)
async def start_run(pile_id: uuid.UUID, request: Request, db: Session = Depends(get_db)) -> Run:
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")

    documents = db.query(Document).filter(Document.pile_id == pile_id).all()
    if not documents:
        raise HTTPException(status_code=400, detail="pile has no documents to run against")

    thread_id = str(uuid.uuid4())
    run = Run(pile_id=pile_id, status="running", thread_id=thread_id)
    db.add(run)
    db.commit()
    db.refresh(run)

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "pile_id": str(pile_id),
        "run_id": str(run.id),
        "document_ids": [str(d.id) for d in documents],
    }

    try:
        await graph.ainvoke(initial_state, config=config)
        run.status = "completed"
    except Exception as exc:  # noqa: BLE001 — surfaced via run.status, not swallowed
        run.status = "failed"
        run.thread_id = f"{thread_id} ({exc})"[:255]
    finally:
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)

    return run


@router.post("/{pile_id}/examine", response_model=RunRead)
async def start_examine(pile_id: uuid.UUID, request: Request, db: Session = Depends(get_db)) -> Run:
    """Movement 2: re-examines facts Movement 1 already extracted against the
    pile's rules. Does not re-parse or re-extract — if you haven't run
    `/runs` yet, there are no facts to check and every rule will honestly
    find nothing, not fail."""
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")

    thread_id = str(uuid.uuid4())
    run = Run(pile_id=pile_id, status="running", thread_id=thread_id)
    db.add(run)
    db.commit()
    db.refresh(run)

    graph = request.app.state.examine_graph
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"pile_id": str(pile_id), "run_id": str(run.id)}

    try:
        await graph.ainvoke(initial_state, config=config)
        run.status = "completed"
    except Exception as exc:  # noqa: BLE001 — surfaced via run.status, not swallowed
        run.status = "failed"
        run.thread_id = f"{thread_id} ({exc})"[:255]
    finally:
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)

    return run


@router.get("/{pile_id}/review", response_model=list[PendingReviewRead])
def list_pending_review(pile_id: uuid.UUID, db: Session = Depends(get_db)) -> list[PendingReview]:
    return (
        db.query(PendingReview)
        .filter(PendingReview.pile_id == pile_id)
        .order_by(PendingReview.created_at.desc())
        .all()
    )


@router.get("/{pile_id}/deliverable", response_model=list[DeliverableSectionRead])
def get_deliverable(pile_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DeliverableSection]:
    return db.query(DeliverableSection).filter(DeliverableSection.pile_id == pile_id).all()


@router.get("/{pile_id}/changelog", response_model=list[ChangelogEntryRead])
def get_changelog(pile_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ChangelogEntry]:
    return (
        db.query(ChangelogEntry)
        .filter(ChangelogEntry.pile_id == pile_id)
        .order_by(ChangelogEntry.changed_at.desc())
        .all()
    )
