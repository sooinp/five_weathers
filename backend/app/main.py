"""
FastAPI application entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from slowapi.errors import RateLimitExceeded
except ModuleNotFoundError:
    class RateLimitExceeded(Exception):
        detail = "Rate limiting is unavailable."

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.db.init_db import init_db

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_LTWR_DIR = _BACKEND_DIR / "data" / "ltwr_maps"
_SIM_MAP_DIR = _BACKEND_DIR / "data" / "sim_map"
_SIM_VIDEO_DIR = _BACKEND_DIR / "data" / "sim_video"


async def _ltwr_hourly_scanner() -> None:
    from app.api.ltwr import scan_ltwr_dir

    while True:
        try:
            import time as _time

            secs = 3600 - (_time.time() % 3600)
            await asyncio.sleep(secs)
            scan_ltwr_dir()
            logger.info("LTWR hourly scan completed")
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("LTWR hourly scan failed")
            await asyncio.sleep(60)


async def _initialize_db_background() -> None:
    try:
        await init_db()
    except Exception:
        logger.exception("DB initialization failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    db_init_task = asyncio.create_task(_initialize_db_background())
    scanner_task = asyncio.create_task(_ltwr_hourly_scanner())
    yield
    scanner_task.cancel()
    db_init_task.cancel()


app = FastAPI(
    title="Fiveweathers UGV Dashboard Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Too many requests. Please retry shortly. ({exc.detail})"},
        headers={"Retry-After": "60"},
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import auth, assets, dashboard, ltwr, missions, operators, runs, sim_map, sim_video, websocket  # noqa: E402

try:
    from app.api import tactical_map  # noqa: E402
except Exception as exc:  # pragma: no cover - optional local dependency path
    tactical_map = None
    logger.warning("Tactical map routes are disabled: %s", exc)

app.include_router(auth.router, prefix="/api")
app.include_router(missions.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(ltwr.router, prefix="/api")
app.include_router(websocket.router)
app.include_router(operators.router, prefix="/api")
app.include_router(sim_map.router, prefix="/api")
app.include_router(sim_video.router, prefix="/api")
if tactical_map is not None:
    app.include_router(tactical_map.router, prefix="/api")

_LTWR_DIR.mkdir(parents=True, exist_ok=True)
_SIM_MAP_DIR.mkdir(parents=True, exist_ok=True)
_SIM_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/ltwr-maps", StaticFiles(directory=str(_LTWR_DIR)), name="ltwr-maps")
app.mount("/sim-maps", StaticFiles(directory=str(_SIM_MAP_DIR)), name="sim-maps")
app.mount("/sim-videos", StaticFiles(directory=str(_SIM_VIDEO_DIR)), name="sim-videos")


@app.get("/", tags=["system"])
async def root():
    return {"message": "Backend is running"}


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
