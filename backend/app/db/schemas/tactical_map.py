"""
backend/app/db/schemas/tactical_map.py

전술 맵 API 전용 Pydantic v2 응답 스키마.
dashboard.py 스키마와 분리 — 맵 표시 데이터 전용.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class GridCell(BaseModel):
    """단일 격자 셀."""
    row: int
    col: int
    value: float


class GridSize(BaseModel):
    ny: int
    nx: int


class MapMetaOut(BaseModel):
    """격자 메타 정보."""
    grid_size: GridSize
    resolution_m: int
    area_km: str
    actual_times: list[str]


class MapLayerOut(BaseModel):
    """
    단일 레이어 응답 — 위험도 / 기동성 / 센서 탭 중 하나.
    cells: threshold 이상인 셀만 포함 (전체 포함 시 10201개).
    """
    layer_type: str                    # "risk" | "mobility" | "sensor"
    time_str: Optional[str] = None     # 실황 기준 시각 (없으면 최신)
    cells: list[GridCell]
    grid_size: GridSize


class MapBaseOut(BaseModel):
    """정적 기반 레이어 (지형 비용)."""
    cells: list[GridCell]
    grid_size: GridSize
    meta: MapMetaOut


class RoutePoint(BaseModel):
    row: int
    col: int


class UnitRoute(BaseModel):
    unit_no: int
    waypoints: list[RoutePoint]


class CommanderMapOut(BaseModel):
    """지휘관 전용 — 모든 제대 경로 포함."""
    base: MapBaseOut
    layer: MapLayerOut
    routes: list[UnitRoute]


class OperatorMapOut(BaseModel):
    """통제관 전용 — 자기 제대 경로만 포함."""
    base: MapBaseOut
    layer: MapLayerOut
    my_route: Optional[UnitRoute] = None
    unit_no: int
