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


@router.get("/{run_id}/stages")
def get_run_stages(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Live per-stage progress: the run's status plus the stages that have
    committed a metric so far (name + duration + cost), so the UI can poll this
    while a background run executes and render each stage landing in real time.
    Each stage row appears only once its node has finished — the frontend knows
    the full ordered stage list and shows the not-yet-present ones as pending."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    report = build_cost_report(db, run_id)
    return {
        "run_id": str(run_id),
        "status": run.status,
        "total_duration_ms": report["total_duration_ms"],
        "stages": report["stages"],
    }
