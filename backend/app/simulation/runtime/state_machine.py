"""
backend/app/simulation/runtime/state_machine.py

UGV 유닛 상태 머신.
상태 전이: STANDBY → MOVING → QUEUED → MOVING → DONE (또는 SOS)
"""

from dataclasses import dataclass, field
from typing import Literal

UnitStatus = Literal["STANDBY", "MOVING", "QUEUED", "SOS", "DONE"]

VALID_TRANSITIONS: dict[UnitStatus, list[UnitStatus]] = {
    "STANDBY": ["MOVING"],
    "MOVING": ["QUEUED", "DONE", "SOS"],
    "QUEUED": ["MOVING", "SOS"],
    "SOS": ["DONE"],
    "DONE": [],
}


@dataclass
class UnitState:
    unit_no: int
    asset_code: str
    status: UnitStatus = "STANDBY"
    lat: float = 0.0
    lon: float = 0.0
    message: str | None = None
    history: list[str] = field(default_factory=list)

    def transition(self, new_status: UnitStatus, message: str | None = None) -> bool:
        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            return False
        self.history.append(self.status)
        self.status = new_status
        self.message = message
        return True
