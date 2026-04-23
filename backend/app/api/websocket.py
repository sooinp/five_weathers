"""
backend/app/api/websocket.py

WS /ws/runs/{run_id}?token=<JWT>

클라이언트가 연결하면 JWT를 검증한 뒤 run_id 기반으로 WebSocketManager에 등록.
인증 실패 시 4001 코드로 즉시 연결 종료.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import _decode_token
from app.core.websocket_manager import ws_manager, mission_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/mission")
async def mission_websocket(ws: WebSocket, token: str | None = None):
    """임무 설정 전용 글로벌 채널 — run_id 없이 로그인 직후 구독."""
    try:
        _decode_token(token)
    except Exception:
        logger.warning("WS mission auth failed")
        await ws.close(code=4001)
        return

    await mission_ws_manager.connect(0, ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await mission_ws_manager.disconnect(0, ws)


@router.websocket("/ws/runs/{run_id}")
async def websocket_endpoint(run_id: int, ws: WebSocket, token: str | None = None):
    # JWT 인증 — query param ?token=<JWT>
    try:
        _decode_token(token)
    except Exception:
        logger.warning("WS auth failed for run_id=%s", run_id)
        await ws.close(code=4001)   # 4001: 인증 실패
        return

    await ws_manager.connect(run_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(run_id, ws)
