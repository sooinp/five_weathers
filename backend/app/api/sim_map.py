"""
backend/app/api/sim_map.py

시뮬레이션 결과 HTML 맵 관리 API.

흐름:
  시뮬레이션 실행 → HTML 생성 → POST /api/map/sim/upload → 저장
  프론트(iframe)  → /sim-maps/current.html 로 표시

엔드포인트 (prefix: /api):
  POST /api/map/sim/upload      — HTML 파일 업로드 (multipart 또는 raw body)
  GET  /api/map/sim/status      — 현재 파일 존재 여부 + 업로드 시각
  DELETE /api/map/sim/clear     — 업로드된 파일 삭제

HTML 파일은 /sim-maps/current.html 로 StaticFiles 서빙.
프론트에서는 <iframe src="/sim-maps/current.html"> 방식으로 임베드.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/map/sim", tags=["sim-map"])

SIM_MAP_DIR = Path(__file__).resolve().parents[2] / "data" / "sim_map"
CURRENT_HTML = SIM_MAP_DIR / "current.html"
CURRENT_URL  = "/sim-maps/current.html"

_uploaded_at: datetime | None = None


def _ensure_dir():
    SIM_MAP_DIR.mkdir(parents=True, exist_ok=True)


# ── 업로드 ────────────────────────────────────────────────

@router.post("/upload", summary="시뮬레이션 결과 HTML 업로드")
async def upload_sim_map(request: Request):
    """
    시뮬레이션 파이프라인이 생성한 HTML 파일을 받아 저장.

    두 가지 방식 모두 지원:
      1) multipart/form-data  — field name: file
      2) raw body (text/html) — Content-Type: text/html 로 직접 전송
    """
    global _uploaded_at
    _ensure_dir()

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload: UploadFile = form.get("file")
        if upload is None:
            raise HTTPException(status_code=422, detail="form field 'file' 필요")
        html_bytes = await upload.read()
    else:
        # raw body
        html_bytes = await request.body()

    if not html_bytes:
        raise HTTPException(status_code=422, detail="빈 파일입니다.")

    CURRENT_HTML.write_bytes(html_bytes)
    _uploaded_at = datetime.now(timezone.utc)

    logger.info("sim_map uploaded: %d bytes at %s", len(html_bytes), _uploaded_at.isoformat())
    return {
        "ok": True,
        "url": CURRENT_URL,
        "size_bytes": len(html_bytes),
        "uploaded_at": _uploaded_at.isoformat(),
    }


# ── 상태 조회 ─────────────────────────────────────────────

@router.get("/status", summary="업로드 파일 상태 조회")
async def get_sim_map_status():
    """현재 업로드된 HTML 파일의 존재 여부와 업로드 시각 반환."""
    exists = CURRENT_HTML.exists()
    return {
        "available": exists,
        "url": CURRENT_URL if exists else None,
        "uploaded_at": _uploaded_at.isoformat() if _uploaded_at else None,
        "size_bytes": CURRENT_HTML.stat().st_size if exists else None,
    }


# ── 삭제 ─────────────────────────────────────────────────

@router.delete("/clear", summary="업로드된 HTML 삭제")
async def clear_sim_map():
    """저장된 current.html 삭제 (초기화)."""
    global _uploaded_at
    if CURRENT_HTML.exists():
        CURRENT_HTML.unlink()
    _uploaded_at = None
    return {"ok": True, "message": "삭제 완료"}
