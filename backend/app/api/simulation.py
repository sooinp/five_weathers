## API 라우터

from fastapi import APIRouter
from app.services.simulation_service import execute_simulation

router = APIRouter()

@router.get("/simulate")
def simulate():
    result = execute_simulation()
    return {"data": result}