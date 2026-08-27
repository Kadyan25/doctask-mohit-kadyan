import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
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
    RunCreate,
    RunRead,
)
from app.config import settings
from app.db.models import ChangelogEntry, DeliverableSection, Document, PendingReview, Pile, Rule, Run
from app.db.session import SessionLocal, get_db
from app.services.document_parser import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/piles", tags=["piles"])

_VALID_LLM_PROVIDERS = {"fake", "anthropic", "gemini"}


def _validate_llm_provider(provider: str | None) -> None:
    if provider is not None and provider not in _VALID_LLM_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"unknown llm_provider {provider!r} — expected one of {sorted(_VALID_LLM_PROVIDERS)}")


async def _execute_graph_run(graph, run_id: str, thread_id: str, initial_state: dict) -> None:
    """Runs a compiled graph to completion in the background, then records the
    final status. Kept separate from the request so the HTTP call can return the
    run id immediately and the UI can poll per-stage progress while it runs — the
    "visible, watchable stages" the system is built around. Each node already
    commits its own RunStageMetric as it finishes (see cost_tracker.timed_node),
    so progress is observable mid-run without any extra plumbing here."""
    config = {"configurable": {"thread_id": thread_id}}
    status = "completed"
    error: str | None = None
    try:
        await graph.ainvoke(initial_state, config=config)
    except Exception as exc:  # noqa: BLE001 — surfaced via run.status, not swallowed
        status = "failed"
        error = str(exc)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is not None:
            run.status = status
            if error:
                run.thread_id = f"{run.thread_id} ({error})"[:255]
            run.completed_at = datetime.now(timezone.utc)
            db.commit()


@router.post("", response_model=PileRead)
def create_pile(payload: PileCreate, db: Session = Depends(get_db)) -> Pile:
    pile = Pile(name=payload.name)
    db.add(pile)
    db.commit()
    db.refresh(pile)

    # Every pile gets a watched folder for free — dropping a file here is the
    # entire Movement 3 trigger, no API call required. payload.watch_folder_path
    # is accepted but overridden: the watcher only looks under WATCH_FOLDER_PATH.
    watch_dir = Path(settings.watch_folder_path) / str(pile.id)
    watch_dir.mkdir(parents=True, exist_ok=True)
    pile.watch_folder_path = str(watch_dir)
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
async def start_run(
    pile_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: RunCreate = RunCreate(),
    db: Session = Depends(get_db),
) -> Run:
    _validate_llm_provider(payload.llm_provider)
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

    # Return the run id now (status "running"); execute the graph in the
    # background so the UI can poll GET /runs/{id}/stages and watch each stage
    # land. Behavior is otherwise identical to the old synchronous run.
    initial_state = {
        "pile_id": str(pile_id),
        "run_id": str(run.id),
        "llm_provider": payload.llm_provider,
        "document_ids": [str(d.id) for d in documents],
    }
    background_tasks.add_task(_execute_graph_run, request.app.state.graph, str(run.id), thread_id, initial_state)
    return run


@router.post("/{pile_id}/examine", response_model=RunRead)
async def start_examine(
    pile_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: RunCreate = RunCreate(),
    db: Session = Depends(get_db),
) -> Run:
    """Movement 2: re-examines facts Movement 1 already extracted against the
    pile's rules. Does not re-parse or re-extract — if you haven't run
    `/runs` yet, there are no facts to check and every rule will honestly
    find nothing, not fail. Runs in the background like /runs so progress polls."""
    _validate_llm_provider(payload.llm_provider)
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")

    thread_id = str(uuid.uuid4())
    run = Run(pile_id=pile_id, status="running", thread_id=thread_id)
    db.add(run)
    db.commit()
    db.refresh(run)

    initial_state = {"pile_id": str(pile_id), "run_id": str(run.id), "llm_provider": payload.llm_provider}
    background_tasks.add_task(
        _execute_graph_run, request.app.state.examine_graph, str(run.id), thread_id, initial_state
    )
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
