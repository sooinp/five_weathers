"""
backend/app/services/event_service.py

실시간 이벤트(alert, queue event, snapshot) DB 저장 + WebSocket 브로드캐스트.
orchestrator/runtime이 이 서비스를 통해 이벤트를 기록/전송.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.db.models.alert import RunAlert
from app.db.models.snapshot import RunStatusSnapshot
from app.db.models.unit_state import RunQueueEvent, RunUnit

logger = logging.getLogger(__name__)


class EventService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_snapshot(self, run_id: int, data: dict) -> RunStatusSnapshot:
        snapshot = RunStatusSnapshot(run_id=run_id, **data)
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        await ws_manager.broadcast(run_id, {"type": "run_status", **data})
        return snapshot

    async def save_alert(
        self, run_id: int, severity: str, alert_type: str, message: str
    ) -> RunAlert:
        alert = RunAlert(
            run_id=run_id,
            severity=severity,
            alert_type=alert_type,
            message=message,
        )
        self.db.add(alert)
        await self.db.commit()
        await ws_manager.broadcast(
            run_id,
            {
                "type": "alert",
                "run_id": run_id,
                "severity": severity,
                "alert_type": alert_type,
                "message": message,
            },
        )
        return alert

    async def upsert_unit(self, run_id: int, unit_no: int, data: dict) -> None:
        from sqlalchemy import select

        result = await self.db.execute(
            select(RunUnit).where(
                RunUnit.run_id == run_id, RunUnit.unit_no == unit_no
            )
        )
        unit = result.scalar_one_or_none()
        if unit is None:
            unit = RunUnit(run_id=run_id, unit_no=unit_no, **data)
            self.db.add(unit)
        else:
            for k, v in data.items():
                setattr(unit, k, v)
        await self.db.commit()
        await ws_manager.broadcast(
            run_id,
            {"type": "unit_update", "run_id": run_id, "unit_no": unit_no, **data},
        )

    async def save_queue_event(
        self,
        run_id: int,
        asset_code: str,
        event_type: str,
        wait_time_sec: int | None = None,
        priority_score: float | None = None,
    ) -> RunQueueEvent:
        event = RunQueueEvent(
            run_id=run_id,
            asset_code=asset_code,
            event_type=event_type,
            wait_time_sec=wait_time_sec,
            priority_score=priority_score,
        )
        self.db.add(event)
        await self.db.commit()
        return event
