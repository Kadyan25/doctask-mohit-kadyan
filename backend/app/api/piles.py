from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import PileCreate, PileRead
from app.db.models import Pile
from app.db.session import get_db

router = APIRouter(prefix="/piles", tags=["piles"])


@router.post("", response_model=PileRead)
def create_pile(payload: PileCreate, db: Session = Depends(get_db)) -> Pile:
    pile = Pile(name=payload.name, watch_folder_path=payload.watch_folder_path)
    db.add(pile)
    db.commit()
    db.refresh(pile)
    return pile


@router.get("/{pile_id}", response_model=PileRead)
def get_pile(pile_id: UUID, db: Session = Depends(get_db)) -> Pile:
    pile = db.get(Pile, pile_id)
    if pile is None:
        raise HTTPException(status_code=404, detail="pile not found")
    return pile


@router.post("/{pile_id}/documents")
def upload_document(pile_id: UUID):
    raise HTTPException(status_code=501, detail="document ingestion lands in Phase 1 (Movement 1)")


@router.post("/{pile_id}/rules")
def submit_rules(pile_id: UUID):
    raise HTTPException(status_code=501, detail="rules/checklist intake lands in Phase 2 (Movement 2)")


@router.post("/{pile_id}/runs")
def start_run(pile_id: UUID):
    raise HTTPException(status_code=501, detail="pipeline runs land in Phase 1 (Movement 1)")


@router.get("/{pile_id}/review")
def list_pending_review(pile_id: UUID):
    raise HTTPException(status_code=501, detail="review queue lands in Phase 1 (Movement 1)")


@router.get("/{pile_id}/deliverable")
def get_deliverable(pile_id: UUID):
    raise HTTPException(status_code=501, detail="deliverable lands in Phase 1 (Movement 1)")


@router.get("/{pile_id}/changelog")
def get_changelog(pile_id: UUID):
    raise HTTPException(status_code=501, detail="changelog lands in Phase 3 (Movement 3)")
