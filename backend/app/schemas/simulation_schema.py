from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class SimulationStartRequest(BaseModel):
    rows: int = Field(default=12, ge=4, le=50)
    cols: int = Field(default=16, ge=4, le=50)
    ugv_count: int = Field(default=6, ge=1, le=30)
    controller_count: int = Field(default=2, ge=1, le=10)
    risk_sensitivity: Literal["낮음", "중간", "높음"] = "중간"
    departure: str = "AOI-START"
    destination: str = "AOI-END"
    step_interval_sec: float = Field(default=1.0, ge=0.2, le=10.0)


class SimulationCommandRequest(BaseModel):
    action: Literal["pause", "resume", "stop", "tick"]


class ApiEnvelope(BaseModel):
    ok: bool = True
    message: str = ""
    data: dict[str, Any] | None = None
