## 0331 기준 DB용 라우터 모음

from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.simulation_schema import SimulationRunCreate

router = APIRouter(prefix="/runs", tags=["runs"])

@router.get("/")
def list_runs(db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT run_id, mission_name, status, total_ugv_count, total_operator_count,
                   unit_count, created_at
            FROM simulation_run
            ORDER BY run_id DESC
        """)
    ).mappings().all()
    return [dict(row) for row in rows]

@router.post("/")
def create_run(payload: SimulationRunCreate, db: Session = Depends(get_db)):
    row = db.execute(
        text("""
            INSERT INTO simulation_run (
                mission_name, status, total_ugv_count, total_operator_count,
                unit_count, created_at
            )
            VALUES (
                :mission_name, 'created', :total_ugv_count, :total_operator_count,
                :unit_count, NOW()
            )
            RETURNING run_id, mission_name, status, total_ugv_count,
                      total_operator_count, unit_count, created_at
        """),
        payload.model_dump(),
    ).mappings().first()

    db.commit()
    return dict(row)