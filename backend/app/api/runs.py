from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: UUID):
    raise HTTPException(status_code=501, detail="run status lands in Phase 1 (Movement 1)")


@router.get("/{run_id}/cost")
def get_run_cost(run_id: UUID):
    raise HTTPException(status_code=501, detail="cost reporting lands in Phase 4")
