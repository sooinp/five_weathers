from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import simulation
from app.services.simulation_runtime import simulation_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await simulation_manager.shutdown()


app = FastAPI(title="FiveWeather Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(simulation.router)
