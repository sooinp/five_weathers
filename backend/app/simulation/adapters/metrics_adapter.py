"""
backend/app/simulation/adapters/metrics_adapter.py

시뮬레이션 KPI 계산 어댑터.

인터페이스:
    입력: route_result, queue_logs, state_changes
    출력: MetricsResult (success_rate, damage_rate, makespan_sec, queue_kpi, bottleneck_index)

현재는 더미 구현.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsResult:
    success_rate: float = 0.0       # 0~100 (%)
    damage_rate: float = 0.0        # 0~100 (%)
    makespan_sec: int = 0
    queue_kpi: dict = field(default_factory=dict)
    bottleneck_index: float = 0.0   # 0~1


def compute_metrics(
    route_result: Any,
    queue_logs: list[dict],
    state_changes: list[dict],
    total_ugv: int = 1,
) -> MetricsResult:
    """
    KPI 계산.
    현재: 더미 반환값.
    """
    return MetricsResult(
        success_rate=round(75.0 + len(queue_logs) * 0.5, 1),
        damage_rate=round(10.0, 1),
        makespan_sec=3600,
        queue_kpi={
            "avg_wait_sec": 120,
            "max_wait_sec": 300,
            "total_events": len(queue_logs),
        },
        bottleneck_index=0.3,
    )
