from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CostReport, RunRead
from app.db.models import Run
from app.db.session import get_db
from app.services.cost_report import build_cost_report

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/{run_id}/cost", response_model=CostReport)
def get_run_cost(run_id: UUID, db: Session = Depends(get_db)) -> CostReport:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return CostReport(**build_cost_report(db, run_id))
