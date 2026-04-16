"""
backend/app/api/ltwr.py

LTWR(기상 예측 지도) 슬롯 관리 API.

GET /api/ltwr/slots          — 현재 T0~T3 슬롯 파일 목록 반환
POST /api/ltwr/reload        — 폴더 재스캔 (수동 갱신)

HTML 파일은 /ltwr-maps/<슬롯>.html 로 StaticFiles 서빙됨.
프론트에서는 <iframe src="/ltwr-maps/T0.html"> 방식으로 임베드.

파일 명명 규칙 (ltwr_maps/ 폴더 기준):
    T0.html  — 현재 시각 (T+0)
    T1.html  — T+1시간 예측
    T2.html  — T+2시간 예측
    T3.html  — T+3시간 예측

1시간 자동 갱신:
    외부에서 ltwr_maps/ 폴더에 새 파일을 넣으면
    스케줄러가 매 정시에 슬롯 테이블을 자동 갱신함.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ltwr", tags=["ltwr"])

LTWR_DIR = Path(__file__).resolve().parents[2] / "data" / "ltwr_maps"
BASE_URL  = "/ltwr-maps"   # StaticFiles mount 경로

SLOTS = ["T0", "T1", "T2", "T3"]
SLOT_LABELS = {
    "T0": "T+0: Present Status",
    "T1": "T+1: Prediction",
    "T2": "T+2: Prediction",
    "T3": "T+3: Prediction",
}

# 슬롯 → 파일 경로 인메모리 테이블
_slot_table: dict[str, str | None] = {s: None for s in SLOTS}
_last_scanned: datetime | None = None


def scan_ltwr_dir() -> None:
    """ltwr_maps/ 폴더를 스캔해서 슬롯 테이블 갱신."""
    global _last_scanned
    LTWR_DIR.mkdir(parents=True, exist_ok=True)
    for slot in SLOTS:
        fpath = LTWR_DIR / f"{slot}.html"
        _slot_table[slot] = f"{BASE_URL}/{slot}.html" if fpath.exists() else None
    _last_scanned = datetime.now(timezone.utc)
    logger.info("LTWR slots scanned: %s", {k: (v is not None) for k, v in _slot_table.items()})


# 서버 시작 시 1회 스캔
scan_ltwr_dir()


class SlotInfo(BaseModel):
    slot: str        # T0 | T1 | T2 | T3
    label: str       # 표시용 레이블
    url: str | None  # iframe src — None이면 파일 없음
    available: bool


class SlotsResponse(BaseModel):
    slots: list[SlotInfo]
    last_scanned: str


@router.get("/slots", response_model=SlotsResponse, summary="LTWR 슬롯 목록")
async def get_slots():
    return SlotsResponse(
        slots=[
            SlotInfo(
                slot=slot,
                label=SLOT_LABELS[slot],
                url=_slot_table[slot],
                available=_slot_table[slot] is not None,
            )
            for slot in SLOTS
        ],
        last_scanned=_last_scanned.isoformat() if _last_scanned else "",
    )


@router.post("/reload", status_code=200, summary="LTWR 슬롯 수동 재스캔")
async def reload_slots():
    scan_ltwr_dir()
    return {"message": "재스캔 완료", "slots": {k: v is not None for k, v in _slot_table.items()}}
