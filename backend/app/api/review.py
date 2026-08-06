from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import PendingReviewRead, ReviewDecision
from app.db.models import ChangelogEntry, Conflict, Finding, PendingReview
from app.db.session import get_db

router = APIRouter(prefix="/review", tags=["review"])


def _apply_decision(item_id: UUID, decision: ReviewDecision, status: str, db: Session) -> PendingReview:
    item = db.get(PendingReview, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="review item not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"review item already {item.status}")

    item.status = status
    item.reviewer = decision.reviewer
    item.reviewed_at = datetime.now(timezone.utc)

    payload = item.payload or {}
    if item.item_type == "conflict" and payload.get("conflict_id"):
        conflict = db.get(Conflict, payload["conflict_id"])
        if conflict is not None:
            conflict.status = status
    elif item.item_type == "finding" and payload.get("finding_id"):
        finding = db.get(Finding, payload["finding_id"])
        if finding is not None:
            finding.status = status

    db.add(
        ChangelogEntry(
            pile_id=item.pile_id,
            section_key=f"review:{item.item_type}",
            change_summary=f"{item.item_type} {status} by {decision.reviewer or 'reviewer'}: {payload.get('description', '')[:200]}",
            source_document_id=None,
        )
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/approve", response_model=PendingReviewRead)
def approve_item(item_id: UUID, decision: ReviewDecision = ReviewDecision(), db: Session = Depends(get_db)) -> PendingReview:
    return _apply_decision(item_id, decision, "approved", db)


@router.post("/{item_id}/reject", response_model=PendingReviewRead)
def reject_item(item_id: UUID, decision: ReviewDecision = ReviewDecision(), db: Session = Depends(get_db)) -> PendingReview:
    return _apply_decision(item_id, decision, "rejected", db)
