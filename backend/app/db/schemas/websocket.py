"""
backend/app/db/schemas/websocket.py

WebSocket 메시지 타입 정의.
handoff 문서 §11 기준.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class RunStatusMsg(BaseModel):
    type: Literal["run_status"] = "run_status"
    run_id: int
    status: str
    phase: str | None = None
    progress_pct: int
    mission_success_rate: float | None = None
    asset_damage_rate: float | None = None
    remaining_time_sec: int | None = None
    aoi_remaining_sec: int | None = None
    queue_length: int = 0
    timestamp: datetime


class UnitUpdateMsg(BaseModel):
    type: Literal["unit_update"] = "unit_update"
    run_id: int
    unit_no: int
    asset_code: str
    status: str
    lat: float | None = None
    lon: float | None = None
    message: str | None = None


class QueueItem(BaseModel):
    asset_code: str
    wait_time_sec: int | None = None
    priority_score: float | None = None


class QueueUpdateMsg(BaseModel):
    type: Literal["queue_update"] = "queue_update"
    run_id: int
    queue_length: int
    items: list[QueueItem] = []


class RouteUpdateMsg(BaseModel):
    type: Literal["route_update"] = "route_update"
    run_id: int
    unit_no: int
    route_type: str
    reason: str | None = None
    route_id: int | None = None


class MapLayerUpdateMsg(BaseModel):
    type: Literal["map_layer_update"] = "map_layer_update"
    run_id: int
    layer_type: str
    time_slot: str | None = None
    layer_id: int | None = None


class AlertMsg(BaseModel):
    type: Literal["alert"] = "alert"
    run_id: int
    severity: str
    alert_type: str
    message: str | None = None
