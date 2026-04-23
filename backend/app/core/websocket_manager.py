"""
backend/app/core/websocket_manager.py

run_id 기반 WebSocket 연결 관리.
시뮬레이션 orchestrator → 연결된 클라이언트로 실시간 메시지 브로드캐스트.
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        # run_id → WebSocket 목록
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, run_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[run_id].append(ws)
        logger.info("WS connected run_id=%d total=%d", run_id, len(self._connections[run_id]))

    async def disconnect(self, run_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(run_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(run_id, None)
        logger.info("WS disconnected run_id=%d", run_id)

    async def broadcast(self, run_id: int, message: dict[str, Any]) -> None:
        """run_id에 연결된 모든 클라이언트에 JSON 메시지 전송."""
        payload = json.dumps(message, default=str, ensure_ascii=False)
        dead: list[WebSocket] = []

        async with self._lock:
            conns = list(self._connections.get(run_id, []))

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(run_id, ws)

    def connection_count(self, run_id: int) -> int:
        return len(self._connections.get(run_id, []))


# 싱글턴 인스턴스 — main.py에서 앱에 주입
ws_manager = WebSocketManager()

# 임무 설정 전용 전역 채널 (run_id 무관, 로그인 직후 구독)
mission_ws_manager = WebSocketManager()
