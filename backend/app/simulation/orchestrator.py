"""
backend/app/simulation/orchestrator.py

시뮬레이션 실행 진입점.
BackgroundTask에서 run_simulation(run_id)를 호출.

── 모드 전환 방법 ─────────────────────────────────────────
환경변수 SIMULATION_MODE 로 제어:
    SIMULATION_MODE=real   → mumt_sim PathFinder3D + SimulationEngine 사용 (기본값)
    SIMULATION_MODE=mock   → mock/dummy_runner.py 사용 (레거시)

Real 모드 구현 순서 (예정):
    1. loaders: load_static_grid / safe_area / weather / risk_layers
    2. ltwr_adapter.compute_ltwr()
    3. pathfinding_adapter.find_paths()
    4. runtime loop (state_machine + queue_manager + replan_engine)
    5. metrics_adapter.compute_metrics()
    6. force_mix_adapter.evaluate_force_mix()
    7. DB 저장 + WebSocket 브로드캐스트
"""

import logging
import os
from datetime import datetime, timezone

from app.db.models.simulation_run import SimulationRun
from app.db.session import AsyncSessionLocal
from app.simulation.contracts import WsEvent, make_event
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# SIMULATION_MODE=real(기본) | mock
_MODE = os.getenv("SIMULATION_MODE", "real").lower()


async def run_simulation(run_id: int) -> None:
    """BackgroundTask 진입점."""
    logger.info("orchestrator: run_id=%d mode=%s starting", run_id, _MODE)

    try:
        if _MODE == "real":
            await _run_real(run_id)
        else:
            await _run_mock(run_id)
    except Exception as exc:
        logger.exception("orchestrator: run_id=%d failed", run_id)
        await _mark_failed(run_id)
        await ws_manager.broadcast(run_id, make_event(WsEvent.RUN_FAILED, run_id, {"error": str(exc)}))


async def _run_mock(run_id: int) -> None:
    """Mock 모드 — dummy_runner로 위임."""
    from app.simulation.mock.dummy_runner import run_dummy
    await run_dummy(run_id)


async def _run_real(run_id: int) -> None:
    """Real 모드 — mumt_sim PathFinder3D + SimulationEngine 사용."""
    from app.simulation.real_runner import run_real
    await run_real(run_id)


async def _mark_failed(run_id: int) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(SimulationRun).where(SimulationRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = "FAILED"
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
