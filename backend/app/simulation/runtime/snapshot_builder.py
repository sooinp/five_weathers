"""
backend/app/simulation/runtime/snapshot_builder.py

run 상태 스냅샷 딕셔너리 생성.
EventService.save_snapshot()에 전달할 data 빌더.
"""

from datetime import datetime, timezone

from app.simulation.runtime.queue_manager import QueueManager
from app.simulation.runtime.state_machine import UnitState


def build_snapshot(
    run_id: int,
    status: str,
    phase: str | None,
    progress_pct: int,
    unit_states: list[UnitState],
    queue: QueueManager,
    mission_success_rate: float | None = None,
    asset_damage_rate: float | None = None,
    remaining_time_sec: int | None = None,
) -> dict:
    """EventService.save_snapshot(run_id, data)에 전달할 딕셔너리 반환."""
    return {
        "status": status,
        "phase": phase,
        "progress_pct": progress_pct,
        "mission_success_rate": mission_success_rate,
        "asset_damage_rate": asset_damage_rate,
        "remaining_time_sec": remaining_time_sec,
        "queue_length": queue.length,
        "timestamp": datetime.now(timezone.utc),
    }
