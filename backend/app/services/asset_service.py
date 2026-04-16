"""
backend/app/services/asset_service.py

데이터 에셋(parquet/tif/geojson 파일 참조) 관리.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.data_asset import DataAsset


class AssetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_asset(
        self, asset_type: str, file_path: str, meta: dict | None = None
    ) -> DataAsset:
        asset = DataAsset(asset_type=asset_type, file_path=file_path, meta=meta)
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_asset(self, asset_id: int) -> DataAsset | None:
        return await self.db.get(DataAsset, asset_id)
