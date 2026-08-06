from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/{item_id}/approve")
def approve_item(item_id: UUID):
    raise HTTPException(status_code=501, detail="review gate lands in Phase 1 (Movement 1)")


@router.post("/{item_id}/reject")
def reject_item(item_id: UUID):
    raise HTTPException(status_code=501, detail="review gate lands in Phase 1 (Movement 1)")
