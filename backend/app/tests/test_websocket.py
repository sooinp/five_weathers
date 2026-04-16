"""
backend/app/tests/test_websocket.py

WebSocket 연결 테스트.
"""

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws


@pytest.mark.asyncio
async def test_ws_connect_and_ping(client: AsyncClient):
    """WebSocket 연결 후 ping → pong 확인."""
    async with aconnect_ws("/ws/runs/1", client) as ws:
        await ws.send_text("ping")
        msg = await ws.receive_text()
        assert msg == "pong"
