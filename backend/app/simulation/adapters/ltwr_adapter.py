"""
backend/app/simulation/adapters/ltwr_adapter.py

LTWR(Land-Terrain-Weather-Road) 위험도 평가 어댑터.

인터페이스:
    입력: static_grid, weather_data, risk_layer_paths
    출력: LtwrResult (risk_map, mobility_map, sensor_map, ltwr_grade, top_drivers)

현재는 더미 구현. 실제 알고리즘으로 교체 시 이 파일만 수정.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LtwrResult:
    risk_map: dict[str, Any] = field(default_factory=dict)
    mobility_map: dict[str, Any] = field(default_factory=dict)
    sensor_map: dict[str, Any] = field(default_factory=dict)
    ltwr_grade: str = "MEDIUM"  # LOW | MEDIUM | HIGH | CRITICAL
    top_drivers: list[str] = field(default_factory=list)


def compute_ltwr(
    static_grid: Any,
    weather_data: dict[str, Any],
    risk_layer_paths: dict[str, str | None],
) -> LtwrResult:
    """
    LTWR 위험도 계산.
    현재: 더미 반환값.
    """
    return LtwrResult(
        risk_map={"source": "dummy", "value": 0.3},
        mobility_map={"source": "dummy", "value": 0.7},
        sensor_map={"source": "dummy", "value": 0.6},
        ltwr_grade="MEDIUM",
        top_drivers=["weather_rain", "road_condition"],
    )
