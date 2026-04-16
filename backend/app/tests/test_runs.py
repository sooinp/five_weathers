"""
backend/app/tests/test_runs.py

시뮬레이션 run 생성/시작/취소 테스트.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_run(auth_client: AsyncClient, mission_id: int):
    resp = await auth_client.post(f"/api/missions/{mission_id}/runs")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "CREATED"
    assert data["mission_id"] == mission_id


@pytest.mark.asyncio
async def test_get_run_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/api/runs/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_run(auth_client: AsyncClient, run_id: int):
    resp = await auth_client.post(f"/api/runs/{run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"
