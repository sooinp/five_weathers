import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.db.models  # noqa: F401
from app.core.security import create_access_token
from app.db.base import Base
from app.db.init_db import seed_admin, seed_default_operators
from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest_asyncio.fixture
async def setup_database():
    await engine.dispose()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_admin(session)
        await seed_default_operators(session)

    yield

    await engine.dispose()


@pytest_asyncio.fixture
async def client(setup_database):
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def auth_client(setup_database):
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        token = create_access_token(subject="1", role="commander")
        async_client.headers["Authorization"] = f"Bearer {token}"
        yield async_client


@pytest_asyncio.fixture
async def mission_id(auth_client: AsyncClient) -> int:
    resp = await auth_client.post(
        "/api/missions",
        json={
            "name": "fixture-mission",
            "total_ugv": 3,
            "max_ugv_count": 4,
            "mission_duration_min": 120,
            "departure_lat": 37.5,
            "departure_lon": 127.0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest_asyncio.fixture
async def run_id(auth_client: AsyncClient, mission_id: int) -> int:
    resp = await auth_client.post(f"/api/missions/{mission_id}/runs")
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
