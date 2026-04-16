"""
backend/app/services/route_service.py

경로 저장/조회 서비스.
orchestrator에서 경로 결과를 DB에 기록할 때 사용.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.route import RunRoute


class RouteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_route(
        self,
        run_id: int,
        unit_no: int,
        route_type: str,
        geojson: dict,
        reason: str | None = None,
    ) -> RunRoute:
        route = RunRoute(
            run_id=run_id,
            unit_no=unit_no,
            route_type=route_type,
            reason=reason,
            geojson=geojson,
        )
        self.db.add(route)
        await self.db.commit()
        await self.db.refresh(route)
        return route
