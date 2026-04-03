## 0331 기준 시뮬레이션 라우터 모음

from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.schemas.simulation_schema import (
    ApiEnvelope,
    SimulationCommandRequest,
    SimulationStartRequest,
)
from app.services.runtime.simulation_runtime import simulation_manager

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])

@router.get("/health", response_model=ApiEnvelope)
async def healthcheck() -> ApiEnvelope:
    return ApiEnvelope(message="backend ok", data={"status": "ok"})

@router.post("/start", response_model=ApiEnvelope)
async def start_simulation(payload: SimulationStartRequest) -> ApiEnvelope:
    run = await simulation_manager.create_run(payload)
    return ApiEnvelope(
        message="simulation started",
        data={"run_id": run.run_id, "snapshot": run.build_snapshot()},
    )

@router.get("/{run_id}", response_model=ApiEnvelope)
async def get_simulation(run_id: str) -> ApiEnvelope:
    run = simulation_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return ApiEnvelope(
        message="simulation found",
        data={"run_id": run.run_id, "status": run.status},
    )

@router.get("/{run_id}/snapshot", response_model=ApiEnvelope)
async def get_snapshot(run_id: str) -> ApiEnvelope:
    run = simulation_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return ApiEnvelope(message="snapshot loaded", data=run.build_snapshot())

@router.post("/{run_id}/command", response_model=ApiEnvelope)
async def send_command(run_id: str, payload: SimulationCommandRequest) -> ApiEnvelope:
    run = simulation_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")

    updated = await simulation_manager.command(run_id, payload.action)
    return ApiEnvelope(
        message=f"command {payload.action} applied",
        data=updated.build_snapshot(),
    )

@router.websocket("/ws/{run_id}")
async def simulation_ws(websocket: WebSocket, run_id: str) -> None:
    run = simulation_manager.get_run(run_id)
    if not run:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    queue = await simulation_manager.add_listener(run_id)

    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except (WebSocketDisconnect, asyncio.CancelledError):
        await simulation_manager.remove_listener(run_id, queue)
    except Exception:
        await simulation_manager.remove_listener(run_id, queue)
        await websocket.close(code=1011)