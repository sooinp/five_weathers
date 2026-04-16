"""
backend/app/simulation/runtime/replan_engine.py

재경로 탐색 엔진.
위험도 임계값 초과 감지 시 pathfinding_adapter 재호출.
"""

import logging
from typing import Any

from app.simulation.adapters.pathfinding_adapter import PathfindingResult, find_paths
from app.simulation.runtime.state_machine import UnitState

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 0.75  # 위험도 임계값 (0~1)


def check_replan_needed(
    unit_states: list[UnitState],
    risk_snapshot: dict[str, float],
) -> list[int]:
    """
    재경로가 필요한 unit_no 목록 반환.
    risk_snapshot: {unit_no: risk_value}
    """
    to_replan = []
    for unit in unit_states:
        risk = risk_snapshot.get(unit.unit_no, 0.0)
        if risk > RISK_THRESHOLD and unit.status == "MOVING":
            to_replan.append(unit.unit_no)
            logger.info(
                "replan triggered: unit_no=%d risk=%.2f", unit.unit_no, risk
            )
    return to_replan


def replan(
    unit_no: int,
    base: dict,
    targets: list[dict],
    risk_layers: dict[str, Any],
) -> PathfindingResult:
    """단일 유닛 재경로 탐색."""
    return find_paths(
        base=base,
        targets=targets,
        risk_layers=risk_layers,
        ugv_count=1,
    )
