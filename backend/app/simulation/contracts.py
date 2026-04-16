"""
backend/app/simulation/contracts.py

시뮬레이션 WebSocket 이벤트 타입 표준 정의.

모든 WS 메시지는 아래 형식을 따른다:
    {
        "type": "<event_type>",
        "run_id": <int>,
        "timestamp": "<ISO8601>",
        "payload": { ... }
    }

이벤트 타입 목록:
    run.started       — 시뮬레이션 시작
    run.progress      — 진행률 업데이트
    snapshot.created  — 상태 스냅샷 저장됨
    kpi.updated       — KPI 값 변경
    queue.updated     — SOS/대기열 변경
    route.updated     — 경로 업데이트
    layer.updated     — 지도 레이어 업데이트
    alert.created     — 경고 발생
    run.finished      — 시뮬레이션 정상 종료
    run.failed        — 시뮬레이션 오류 종료
"""

from datetime import datetime, timezone
from typing import Any


# ── 이벤트 타입 상수 ──────────────────────────────────────
class WsEvent:
    RUN_STARTED      = "run.started"
    RUN_PROGRESS     = "run.progress"
    SNAPSHOT_CREATED = "snapshot.created"
    KPI_UPDATED      = "kpi.updated"
    QUEUE_UPDATED    = "queue.updated"
    ROUTE_UPDATED    = "route.updated"
    LAYER_UPDATED    = "layer.updated"
    ALERT_CREATED    = "alert.created"
    RUN_FINISHED     = "run.finished"
    RUN_FAILED       = "run.failed"


def make_event(event_type: str, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """표준 WS 이벤트 메시지 생성."""
    return {
        "type": event_type,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
