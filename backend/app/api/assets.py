"""
backend/app/api/assets.py

데이터 에셋 등록/조회 (관리자용).

POST /api/assets          — 에셋 등록 (파일 경로 + 타입 + 메타)
GET  /api/assets/{id}     — 에셋 조회
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetCreate(BaseModel):
    asset_type: str
    file_path: str
    meta: dict | None = None


class AssetOut(BaseModel):
    id: int
    asset_type: str
    file_path: str
    meta: dict | None

    model_config = {"from_attributes": True}


@router.post("", response_model=AssetOut, status_code=201, summary="에셋 등록")
async def create_asset(body: AssetCreate, db: DBSession, user: CurrentUser):
    svc = AssetService(db)
    return await svc.create_asset(body.asset_type, body.file_path, body.meta)


@router.get("/{asset_id}", response_model=AssetOut, summary="에셋 조회")
async def get_asset(asset_id: int, db: DBSession, user: CurrentUser):
    svc = AssetService(db)
    asset = await svc.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="에셋을 찾을 수 없습니다.")
    return asset
