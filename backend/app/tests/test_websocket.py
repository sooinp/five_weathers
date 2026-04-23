import socket
import threading
import time

import pytest
import uvicorn
import websockets

from app.core.security import create_access_token
from app.main import app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(port: int) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return server, thread
        except OSError:
            time.sleep(0.1)

    raise RuntimeError("uvicorn test server did not start in time")


@pytest.mark.asyncio
async def test_ws_connect_and_ping():
    port = _find_free_port()
    server, thread = _start_server(port)
    token = create_access_token(subject="1", role="commander")

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws/runs/1?token={token}") as ws:
            await ws.send("ping")
            assert await ws.recv() == "pong"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
