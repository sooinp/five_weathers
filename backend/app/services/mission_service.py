"""
backend/app/services/mission_service.py

임무 생성/수정/조회 + 목적지 및 force mix 후보 관리.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.mission import Mission, MissionForceMixCandidate, MissionTarget
from app.db.schemas.mission import (
    ForceMixCandidateIn,
    MissionCreate,
    MissionPatch,
    MissionTargetIn,
)


class MissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_mission(self, user_id: int, data: MissionCreate) -> Mission:
        dump = data.model_dump()
        # max_ugv_count 미입력 시 total_ugv 값 사용
        if dump.get("max_ugv_count") is None:
            dump["max_ugv_count"] = dump["total_ugv"]
        mission = Mission(user_id=user_id, **dump)
        self.db.add(mission)
        await self.db.commit()
        await self.db.refresh(mission)
        return await self._load_full(mission.id)

    async def get_mission(self, mission_id: int) -> Mission | None:
        return await self._load_full(mission_id)

    async def patch_mission(self, mission_id: int, data: MissionPatch) -> Mission | None:
        mission = await self.db.get(Mission, mission_id)
        if mission is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(mission, field, value)
        await self.db.commit()
        return await self._load_full(mission_id)

    async def set_targets(
        self, mission_id: int, targets: list[MissionTargetIn]
    ) -> list[MissionTarget]:
        await self.db.execute(
            delete(MissionTarget).where(MissionTarget.mission_id == mission_id)
        )
        new_targets = [
            MissionTarget(
                mission_id=mission_id,
                seq=t.seq,
                lat=t.lat,
                lon=t.lon,
                patrol_duration_sec=t.patrol_duration_sec,
            )
            for t in targets
        ]
        self.db.add_all(new_targets)
        await self.db.commit()
        for t in new_targets:
            await self.db.refresh(t)
        return new_targets

    async def add_force_mix_candidate(
        self, mission_id: int, data: ForceMixCandidateIn
    ) -> MissionForceMixCandidate:
        candidate = MissionForceMixCandidate(mission_id=mission_id, **data.model_dump())
        self.db.add(candidate)
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate

    async def _load_full(self, mission_id: int) -> Mission | None:
        result = await self.db.execute(
            select(Mission)
            .options(
                selectinload(Mission.targets),
                selectinload(Mission.force_mix_candidates),
            )
            .where(Mission.id == mission_id)
        )
        return result.scalar_one_or_none()
