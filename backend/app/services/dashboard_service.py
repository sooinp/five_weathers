"""
backend/app/services/dashboard_service.py

대시보드 조회 서비스.
run_id 기준으로 각 테이블에서 데이터 조회.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.alert import RunAlert
from app.db.models.mission import Mission, MissionTarget
from app.db.models.patrol import RunPatrolEvent
from app.db.models.route import RunKpi, RunMapLayer, RunRecommendation, RunRoute, RunRouteEffect
from app.db.models.run_asset_status import RunAssetStatus
from app.db.models.simulation_run import SimulationRun
from app.db.models.snapshot import RunStatusSnapshot, RunTimeSeriesPanel
from app.db.models.unit_state import RunQueueEvent, RunSosEvent, RunUnit
from app.db.models.user import User
from app.db.schemas.dashboard import (
    LAYER_LABEL,
    LTWR_SLOT_LABEL,
    AcknowledgeResultOut,
    AssetStatusItemOut,
    AssetStatusListOut,
    AssetStatusPatchIn,
    AssetStatusSummaryOut,
    CommanderActionResultOut,
    CommanderActionState,
    CommanderDashboardOut,
    CommanderEchelonsOut,
    CommanderHomeOut,
    CommanderMapHeaderOut,
    CommanderMapMarkerOut,
    CommanderMapOut,
    CommanderMetricOut,
    CommanderModeItem,
    CommanderPanelsOut,
    CommanderRouteLineOut,
    CommanderSetupMapOut,
    CommanderSetupOut,
    CommanderSetupRowOut,
    CommanderSetupTargetItem,
    DispatchResultOut,
    EchelonRowOut,
    HomeAssetModeItem,
    HomeSummaryOut,
    LtwrSlotOut,
    LtwrViewOut,
    MapLayerInfo,
    MapMarker,
    MapViewOut,
    MissionSuccessRateOut,
    OperatorAssetPanelOut,
    OperatorBriefingOut,
    OperatorDashboardOut,
    PatrolAreaItem,
    PatrolAreaOut,
    QueueActiveItem,
    QueueActiveOut,
    RemainingTimeOut,
    RouteEffectOut,
    RunStatusOut,
    SnapshotOut,
    SosQueueItem,
    SosQueueOut,
    SuccessRatePoint,
    UgvCountOut,
    UnitInfoOut,
)


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_run_status(self, run_id: int) -> RunStatusOut | None:
        """
        GET /api/runs/{run_id}/status 전용.
        최신 snapshot + mission.mission_duration_min 을 조합하여 반환.
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        snapshot = await self.latest_snapshot(run_id)
        snapshot_out = SnapshotOut.model_validate(snapshot) if snapshot else None

        return RunStatusOut.from_snapshot_and_mission(
            run_id=run_id,
            status=run.status,
            snapshot=snapshot_out,
            mission_duration_min=mission.mission_duration_min if mission else None,
        )

    async def latest_snapshot(self, run_id: int) -> RunStatusSnapshot | None:
        result = await self.db.execute(
            select(RunStatusSnapshot)
            .where(RunStatusSnapshot.run_id == run_id)
            .order_by(RunStatusSnapshot.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_remaining_time(self, run_id: int) -> RemainingTimeOut | None:
        """
        GET /api/runs/{run_id}/remaining-time 전용.

        snapshot 없이 started_at 기준으로 서버에서 직접 계산.
        → 매 호출마다 실시간 정확한 값 반환.

        상태별 동작:
          CREATED   → elapsed=0,  remaining=total  (아직 시작 안 함)
          RUNNING   → 실시간 계산
          COMPLETED/FAILED/CANCELLED → elapsed=total, remaining=0
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        total_sec = (mission.mission_duration_min * 60) if mission else 0
        now = datetime.now(timezone.utc)

        # 경과 시간 계산
        if run.status == "RUNNING" and run.started_at:
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed_sec = max(0, int((now - started).total_seconds()))

        elif run.status in ("COMPLETED", "FAILED", "CANCELLED"):
            # 종료된 run: 전체 시간만큼 경과
            elapsed_sec = total_sec

        else:
            # CREATED 또는 started_at 없음: 아직 시작 전
            elapsed_sec = 0

        remaining_sec = max(0, total_sec - elapsed_sec)
        progress_pct = round(elapsed_sec / total_sec * 100, 1) if total_sec > 0 else 0.0

        def to_hms(sec: int) -> str:
            h, r = divmod(sec, 3600)
            m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        from app.db.schemas.dashboard import STATUS_LABEL

        return RemainingTimeOut(
            run_id=run_id,
            status=run.status,
            status_label=STATUS_LABEL.get(run.status, run.status),
            total_sec=total_sec,
            total_hms=to_hms(total_sec),
            elapsed_sec=elapsed_sec,
            elapsed_hms=to_hms(elapsed_sec),
            remaining_sec=remaining_sec,
            remaining_hms=to_hms(remaining_sec),
            progress_pct=progress_pct,
            is_expired=(remaining_sec == 0 and run.status == "RUNNING"),
            started_at=run.started_at,
            calculated_at=now,
        )

    async def get_active_queue(self, run_id: int) -> QueueActiveOut | None:
        """
        GET /api/runs/{run_id}/queue/active 전용.

        로직:
          1. run_units에서 status='QUEUED' 인 유닛 목록 조회
          2. 각 유닛별 run_queue_events에서 가장 최근 ENTER 이벤트 조회
          3. 경과 시간(elapsed) = 현재시각 - entered_at
          4. priority_score, wait_time_sec는 ENTER 이벤트에서 가져옴
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        # 1. 현재 QUEUED 상태 유닛 목록
        units_result = await self.db.execute(
            select(RunUnit).where(
                RunUnit.run_id == run_id,
                RunUnit.status == "QUEUED",
            )
        )
        queued_units: list[RunUnit] = list(units_result.scalars().all())

        now = datetime.now(timezone.utc)
        items: list[QueueActiveItem] = []

        for unit in queued_units:
            # 2. 해당 유닛의 최신 ENTER 이벤트 조회
            evt_result = await self.db.execute(
                select(RunQueueEvent)
                .where(
                    RunQueueEvent.run_id == run_id,
                    RunQueueEvent.asset_code == unit.asset_code,
                    RunQueueEvent.event_type == "ENTER",
                )
                .order_by(RunQueueEvent.timestamp.desc())
                .limit(1)
            )
            enter_event = evt_result.scalar_one_or_none()

            # ENTER 이벤트가 없으면 unit.updated_at을 fallback으로 사용
            entered_at = (
                enter_event.timestamp if enter_event else unit.updated_at
            )
            # timezone-aware 비교
            if entered_at.tzinfo is None:
                entered_at = entered_at.replace(tzinfo=timezone.utc)

            elapsed_sec = max(0, int((now - entered_at).total_seconds()))

            wait_sec = enter_event.wait_time_sec if enter_event else None
            p_score = enter_event.priority_score if enter_event else None

            items.append(
                QueueActiveItem(
                    asset_code=unit.asset_code,
                    unit_no=unit.unit_no,
                    entered_at=entered_at,
                    elapsed_sec=elapsed_sec,
                    elapsed_min=elapsed_sec // 60,
                    wait_time_sec=wait_sec,
                    wait_time_min=wait_sec // 60 if wait_sec is not None else None,
                    priority_score=p_score,
                    lat=unit.lat,
                    lon=unit.lon,
                )
            )

        # elapsed_sec 내림차순 정렬 (오래 기다린 순)
        items.sort(key=lambda x: x.elapsed_sec, reverse=True)

        return QueueActiveOut(
            run_id=run_id,
            active_count=len(items),
            items=items,
        )

    async def get_success_rate(self, run_id: int) -> MissionSuccessRateOut | None:
        """
        GET /api/runs/{run_id}/success-rate 전용.

        - current  : 최신 snapshot.mission_success_rate
        - history  : 스냅샷 전체 시계열 (최대 100개, 시간 오름차순)
        - projected: 패널 테이블에서 T1/T2/T3 슬롯별 최신 success_rate 추출
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        # 1. 현재값 — 최신 스냅샷 1개
        latest = await self.latest_snapshot(run_id)
        current = latest.mission_success_rate if latest else None

        # 2. 시계열 이력 — 시간 오름차순, 최대 100개
        hist_result = await self.db.execute(
            select(RunStatusSnapshot)
            .where(
                RunStatusSnapshot.run_id == run_id,
                RunStatusSnapshot.mission_success_rate.is_not(None),
            )
            .order_by(RunStatusSnapshot.timestamp.asc())
            .limit(100)
        )
        history: list[SuccessRatePoint] = [
            SuccessRatePoint(timestamp=row.timestamp, value=row.mission_success_rate)
            for row in hist_result.scalars().all()
        ]

        # 3. 예측값 — run_time_series_panels 각 슬롯의 최신 레코드
        projected: dict[str, float | None] = {}
        for slot in ("T1", "T2", "T3"):
            panel_result = await self.db.execute(
                select(RunTimeSeriesPanel)
                .where(
                    RunTimeSeriesPanel.run_id == run_id,
                    RunTimeSeriesPanel.panel_type == slot,
                )
                .order_by(RunTimeSeriesPanel.timestamp.desc())
                .limit(1)
            )
            panel = panel_result.scalar_one_or_none()
            if panel and panel.data:
                projected[slot] = panel.data.get("success_rate")
            else:
                projected[slot] = None

        return MissionSuccessRateOut(
            run_id=run_id,
            current=current,
            history=history,
            projected=projected,
        )

    async def get_panels(self, run_id: int) -> list[RunTimeSeriesPanel]:
        result = await self.db.execute(
            select(RunTimeSeriesPanel)
            .where(RunTimeSeriesPanel.run_id == run_id)
            .order_by(RunTimeSeriesPanel.panel_type)
        )
        return list(result.scalars().all())

    async def get_units(self, run_id: int) -> list[RunUnit]:
        result = await self.db.execute(
            select(RunUnit)
            .where(RunUnit.run_id == run_id)
            .order_by(RunUnit.unit_no)
        )
        return list(result.scalars().all())

    async def get_queue_events(self, run_id: int) -> list[RunQueueEvent]:
        result = await self.db.execute(
            select(RunQueueEvent)
            .where(RunQueueEvent.run_id == run_id)
            .order_by(RunQueueEvent.timestamp.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_routes(self, run_id: int) -> list[RunRoute]:
        result = await self.db.execute(
            select(RunRoute).where(RunRoute.run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_map_layers(self, run_id: int) -> list[RunMapLayer]:
        result = await self.db.execute(
            select(RunMapLayer).where(RunMapLayer.run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_alerts(self, run_id: int) -> list[RunAlert]:
        result = await self.db.execute(
            select(RunAlert)
            .where(RunAlert.run_id == run_id)
            .order_by(RunAlert.timestamp.desc())
        )
        return list(result.scalars().all())

    async def get_kpis(self, run_id: int) -> list[RunKpi]:
        result = await self.db.execute(
            select(RunKpi).where(RunKpi.run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_danger_queue(self, run_id: int) -> SosQueueOut | None:
        """
        GET /api/runs/{run_id}/queue/danger 전용.

        로직:
          1. run_sos_events에서 해당 run의 SOS 이벤트 전체 조회
          2. resolved_at IS NULL = 아직 대기 중 → danger_count 집계
          3. sos_at 오름차순 정렬 → FIFO 순서 (fifo_position)
          4. elapsed = now - sos_at (카운트업)
          5. 처리 완료(resolved_at 있음) 항목도 포함하여 이력 제공
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        result = await self.db.execute(
            select(RunSosEvent)
            .where(RunSosEvent.run_id == run_id)
            .order_by(RunSosEvent.sos_at.asc())   # FIFO: 먼저 SOS 발생 순
        )
        events: list[RunSosEvent] = list(result.scalars().all())

        now = datetime.now(timezone.utc)

        def to_hms(sec: int) -> str:
            h, r = divmod(sec, 3600)
            m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        items: list[SosQueueItem] = []
        for pos, evt in enumerate(events, start=1):
            is_resolved = evt.resolved_at is not None

            sos_at = evt.sos_at
            if sos_at.tzinfo is None:
                sos_at = sos_at.replace(tzinfo=timezone.utc)

            if is_resolved:
                resolved = evt.resolved_at
                if resolved.tzinfo is None:
                    resolved = resolved.replace(tzinfo=timezone.utc)
                elapsed_sec = max(0, int((resolved - sos_at).total_seconds()))
            else:
                elapsed_sec = max(0, int((now - sos_at).total_seconds()))

            items.append(
                SosQueueItem(
                    sos_event_id=evt.id,
                    unit_no=evt.unit_no,
                    asset_code=evt.asset_code,
                    sos_at=sos_at,
                    elapsed_sec=elapsed_sec,
                    elapsed_min=elapsed_sec // 60,
                    elapsed_hms=to_hms(elapsed_sec),
                    fifo_position=pos,
                    is_resolved=is_resolved,
                    resolved_at=evt.resolved_at,
                    lat=evt.lat,
                    lon=evt.lon,
                    calculated_at=now,
                )
            )

        danger_count = sum(1 for i in items if not i.is_resolved)

        return SosQueueOut(
            run_id=run_id,
            danger_count=danger_count,
            items=items,
        )

    async def get_route_effect(self, run_id: int) -> RouteEffectOut | None:
        """
        GET /api/runs/{run_id}/route-effect 전용.

        run_route_effects에서 해당 run의 가장 최신 레코드를 조회.
        delta_label 은 서버에서 포맷팅하여 반환 (예: "+12%", "-7%").
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        result = await self.db.execute(
            select(RunRouteEffect)
            .where(RunRouteEffect.run_id == run_id)
            .order_by(RunRouteEffect.created_at.desc())
            .limit(1)
        )
        effect = result.scalar_one_or_none()

        if effect is None:
            # 아직 효과 데이터 없음 → 빈 응답 반환 (404 아님)
            return RouteEffectOut(run_id=run_id)

        def fmt_delta(val: float | None) -> str | None:
            if val is None:
                return None
            return f"+{val:.1f}%" if val >= 0 else f"{val:.1f}%"

        return RouteEffectOut(
            run_id=run_id,
            optimal_success_rate=effect.optimal_success_rate,
            optimal_damage_rate=effect.optimal_damage_rate,
            alt_success_rate=effect.alt_success_rate,
            alt_damage_rate=effect.alt_damage_rate,
            success_rate_delta=effect.success_rate_delta,
            success_rate_delta_label=fmt_delta(effect.success_rate_delta),
            damage_rate_delta=effect.damage_rate_delta,
            damage_rate_delta_label=fmt_delta(effect.damage_rate_delta),
            created_at=effect.created_at,
        )

    async def get_ugv_count(self, run_id: int) -> UgvCountOut | None:
        """
        GET /api/runs/{run_id}/ugv-count 전용.

        - total_ugv    : mission 입력값 (0~4대, 사용자 결정)
        - max_ugv_count: 편성 최대값
        - 실시간 상태별 분류: run_units 테이블에서 집계
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        if mission is None:
            return None

        units_result = await self.db.execute(
            select(RunUnit).where(RunUnit.run_id == run_id)
        )
        units: list[RunUnit] = list(units_result.scalars().all())

        active_count = sum(1 for u in units if u.status in ("MOVING", "STANDBY"))
        queued_count = sum(1 for u in units if u.status == "QUEUED")
        done_count   = sum(1 for u in units if u.status == "DONE")
        sos_count    = sum(1 for u in units if u.status == "SOS")

        return UgvCountOut(
            run_id=run_id,
            mission_id=mission.id,
            total_ugv=mission.total_ugv,
            max_ugv_count=mission.max_ugv_count,
            active_count=active_count,
            queued_count=queued_count,
            done_count=done_count,
            sos_count=sos_count,
        )

    async def get_unit_info(self, run_id: int) -> UnitInfoOut | None:
        """
        GET /api/runs/{run_id}/unit-info 전용.

        run → mission 에서 echelon_no / total_ugv / max_ugv_count 조회.
        echelon_label = f"{echelon_no}제대" 로 자동 생성.
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        if mission is None:
            return None

        return UnitInfoOut(
            run_id=run_id,
            mission_id=mission.id,
            echelon_no=mission.echelon_no,
            echelon_label=f"{mission.echelon_no}제대",
            total_ugv=mission.total_ugv,
            max_ugv_count=mission.max_ugv_count,
        )

    async def get_recommendations(self, run_id: int) -> list[RunRecommendation]:
        result = await self.db.execute(
            select(RunRecommendation).where(RunRecommendation.run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_patrol_area(self, run_id: int) -> PatrolAreaOut | None:
        """
        GET /api/runs/{run_id}/patrol-area 전용.

        로직:
          1. run_patrol_events 전체 조회 (해당 run_id)
          2. 각 이벤트별 arrived_at 기준 카운트다운 계산
             - is_completed=False(정찰 중): 실시간 remaining 계산
             - is_completed=True(정찰 완료): remaining=0, progress=100
          3. active_count = completed_at IS NULL인 항목 수
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        result = await self.db.execute(
            select(RunPatrolEvent)
            .where(RunPatrolEvent.run_id == run_id)
            .order_by(RunPatrolEvent.arrived_at.asc())
        )
        events: list[RunPatrolEvent] = list(result.scalars().all())

        now = datetime.now(timezone.utc)

        def to_hms(sec: int) -> str:
            h, r = divmod(sec, 3600)
            m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        items: list[PatrolAreaItem] = []
        for evt in events:
            total = evt.patrol_duration_sec
            is_completed = evt.completed_at is not None

            arrived = evt.arrived_at
            if arrived.tzinfo is None:
                arrived = arrived.replace(tzinfo=timezone.utc)

            if is_completed:
                elapsed_sec = total
                remaining_sec = 0
                progress_pct = 100.0
                is_expired = False
            else:
                elapsed_sec = max(0, int((now - arrived).total_seconds()))
                remaining_sec = max(0, total - elapsed_sec)
                progress_pct = round(elapsed_sec / total * 100, 1) if total > 0 else 0.0
                is_expired = remaining_sec == 0 and run.status == "RUNNING"

            items.append(
                PatrolAreaItem(
                    event_id=evt.id,
                    run_id=evt.run_id,
                    unit_no=evt.unit_no,
                    asset_code=evt.asset_code,
                    target_seq=evt.target_seq,
                    target_lat=evt.target_lat,
                    target_lon=evt.target_lon,
                    patrol_duration_sec=total,
                    patrol_duration_hms=to_hms(total),
                    arrived_at=arrived,
                    is_completed=is_completed,
                    elapsed_sec=min(elapsed_sec, total),
                    elapsed_hms=to_hms(min(elapsed_sec, total)),
                    remaining_sec=remaining_sec,
                    remaining_hms=to_hms(remaining_sec),
                    progress_pct=min(100.0, progress_pct),
                    is_expired=is_expired,
                    calculated_at=now,
                )
            )

        active_count = sum(1 for i in items if not i.is_completed)

        return PatrolAreaOut(
            run_id=run_id,
            active_count=active_count,
            total_count=len(items),
            items=items,
        )

    async def get_map_view(self, run_id: int) -> MapViewOut | None:
        """
        GET /api/runs/{run_id}/map-view 전용.

        로직:
          1. run → mission 조회 (출발지 좌표, 목적지 목록)
          2. run_map_layers 에서 RISK / MOBILITY / SENSOR 최신 레이어 조회
          3. run_units 에서 현재 UGV 위치/상태 조회
          4. 레이어 3종 + 마커(출발지/도착지/UGV) 조합하여 반환
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        if mission is None:
            return None

        # 목적지 목록 조회 (seq 오름차순)
        targets_result = await self.db.execute(
            select(MissionTarget)
            .where(MissionTarget.mission_id == mission.id)
            .order_by(MissionTarget.seq.asc())
        )
        targets: list[MissionTarget] = list(targets_result.scalars().all())

        # 레이어 3종: 각 타입별 최신 1개 조회
        layers: list[MapLayerInfo] = []
        for layer_type in ("RISK", "MOBILITY", "SENSOR"):
            layer_result = await self.db.execute(
                select(RunMapLayer)
                .where(
                    RunMapLayer.run_id == run_id,
                    RunMapLayer.layer_type == layer_type,
                )
                .order_by(RunMapLayer.created_at.desc())
                .limit(1)
            )
            layer = layer_result.scalar_one_or_none()
            layers.append(
                MapLayerInfo(
                    layer_type=layer_type,
                    layer_label=LAYER_LABEL.get(layer_type, layer_type),
                    file_path=layer.file_path if layer else None,
                    meta=layer.meta if layer else None,
                    is_ready=layer is not None and layer.file_path is not None,
                )
            )

        # 마커 조합
        markers: list[MapMarker] = []

        # 출발지 마커
        markers.append(
            MapMarker(
                marker_type="DEPARTURE",
                label="출발지",
                lat=mission.departure_lat,
                lon=mission.departure_lon,
            )
        )

        # 도착지(목적지) 마커
        for t in targets:
            markers.append(
                MapMarker(
                    marker_type="TARGET",
                    label=f"도착지{t.seq}" if len(targets) > 1 else "도착지",
                    lat=t.lat,
                    lon=t.lon,
                    seq=t.seq,
                )
            )

        # UGV 마커 (현재 위치)
        units_result = await self.db.execute(
            select(RunUnit)
            .where(RunUnit.run_id == run_id)
            .order_by(RunUnit.unit_no.asc())
        )
        units: list[RunUnit] = list(units_result.scalars().all())
        for unit in units:
            if unit.lat is not None and unit.lon is not None:
                markers.append(
                    MapMarker(
                        marker_type="UGV",
                        label=unit.asset_code,
                        unit_no=unit.unit_no,
                        lat=unit.lat,
                        lon=unit.lon,
                        status=unit.status,
                    )
                )

        return MapViewOut(
            run_id=run_id,
            mission_id=mission.id,
            layers=layers,
            markers=markers,
            center_lat=mission.departure_lat,
            center_lon=mission.departure_lon,
        )

    async def get_ltwr_view(self, run_id: int) -> LtwrViewOut | None:
        """
        GET /api/runs/{run_id}/ltwr-view 전용.

        로직:
          1. run 존재 확인
          2. T0~T3 각 슬롯별로 run_map_layers 에서 layer_type='LTWR' 최신 1개 조회
          3. 슬롯 파일이 없으면 is_ready=False (수신 대기 중)
          4. T0 → T1 → T2 → T3 순서로 고정 반환 (항상 4개 슬롯)
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        slots: list[LtwrSlotOut] = []
        for time_slot in ("T0", "T1", "T2", "T3"):
            layer_result = await self.db.execute(
                select(RunMapLayer)
                .where(
                    RunMapLayer.run_id == run_id,
                    RunMapLayer.layer_type == "LTWR",
                    RunMapLayer.time_slot == time_slot,
                )
                .order_by(RunMapLayer.created_at.desc())
                .limit(1)
            )
            layer = layer_result.scalar_one_or_none()
            slots.append(
                LtwrSlotOut(
                    time_slot=time_slot,
                    slot_label=LTWR_SLOT_LABEL[time_slot],
                    file_path=layer.file_path if layer else None,
                    meta=layer.meta if layer else None,
                    is_ready=layer is not None and layer.file_path is not None,
                    created_at=layer.created_at if layer else None,
                )
            )

        ready_count = sum(1 for s in slots if s.is_ready)
        return LtwrViewOut(
            run_id=run_id,
            slots=slots,
            ready_count=ready_count,
        )
    
    async def get_home_summary(self, user_id: int) -> HomeSummaryOut | None:
        user = await self.db.get(User, user_id)
        if user is None:
            return None

        now = datetime.now()
        current_time = now.strftime("%Y.%m.%d %H:%M")

        role = (user.role or "").lower()

        # 최신 run / mission 조회
        latest_run_result = await self.db.execute(
            select(SimulationRun)
            .join(Mission, SimulationRun.mission_id == Mission.id)
            .where(Mission.user_id == user_id)
            .order_by(SimulationRun.created_at.desc())
            .limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()
        latest_run_id = latest_run.id if latest_run else None
        latest_mission_id = latest_run.mission_id if latest_run else None
        has_pending_briefing = (
            latest_run is not None
            and latest_run.dispatched_at is not None
            and latest_run.acknowledged_at is None
        )

        if role == "commander":
            return HomeSummaryOut(
                role="commander",
                role_label="지휘관",
                current_time=current_time,
                remaining_time="02:00:34",
                mission_notice=None,
                unit_label=None,
                asset_status_label="자산현황",
                asset_modes=[
                    HomeAssetModeItem(key="balanced", label="균형", count=3),
                    HomeAssetModeItem(key="recon", label="정찰", count=3),
                    HomeAssetModeItem(key="rapid", label="신속", count=3),
                ],
                selected_mode=latest_run.selected_mode if latest_run and latest_run.selected_mode else "balanced",
                latest_run_id=latest_run_id,
                latest_mission_id=latest_mission_id,
                has_pending_briefing=has_pending_briefing,
                assigned_echelon_no=None,
            )

        # operator = 통제관
        # 본인 mission의 echelon_no 조회
        echelon_no: int | None = None
        if latest_mission_id:
            mission = await self.db.get(Mission, latest_mission_id)
            echelon_no = mission.echelon_no if mission else None

        return HomeSummaryOut(
            role="operator",
            role_label="통제관",
            current_time=current_time,
            remaining_time="02:00:34",
            mission_notice="임무를 하달받았습니다." if has_pending_briefing else None,
            unit_label=f"{echelon_no}제대" if echelon_no else "제대1",
            asset_status_label="자산현황",
            asset_modes=[
                HomeAssetModeItem(key="balanced", label="균형", count=3),
            ],
            selected_mode=latest_run.selected_mode if latest_run and latest_run.selected_mode else "balanced",
            latest_run_id=latest_run_id,
            latest_mission_id=latest_mission_id,
            has_pending_briefing=has_pending_briefing,
            assigned_echelon_no=echelon_no,
        )
    
    async def get_commander_home(self, run_id: int) -> CommanderHomeOut | None:
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        latest = await self.latest_snapshot(run_id)

        success_rate = latest.mission_success_rate if latest else None
        risk_rate = latest.asset_damage_rate if latest and latest.asset_damage_rate is not None else None

        return CommanderHomeOut(
            run_id=run_id,
            role_label="지휘관",
            tabs=["지휘관", "자산 현황"],
            selected_tab="지휘관",
            modes=[
                CommanderModeItem(key="balanced", label="균형", selected=True),
                CommanderModeItem(key="recon", label="정찰", selected=False),
                CommanderModeItem(key="rapid", label="신속", selected=False),
            ],
            selected_mode="balanced",
            metrics=CommanderMetricOut(
                success_rate=success_rate,
                risk_rate=risk_rate,
            ),
            actions=CommanderActionState(
                execute_enabled=run.status in ("CREATED", "READY"),
                terminate_enabled=run.status in ("RUNNING",),
                dispatch_enabled=run.status in ("CREATED", "READY"),
                replan_enabled=run.status in ("RUNNING", "COMPLETED"),
            ),
        )
    
    async def get_commander_echelons(self, run_id: int) -> CommanderEchelonsOut | None:
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        # 현재 DB가 제대 단위 ETA를 직접 안 갖고 있을 가능성이 높아서
        # 1차는 하드코딩 또는 mission/route 데이터 조합으로 시작
        rows = [
            EchelonRowOut(
                echelon_id=1,
                echelon_label="1제대",
                ugv_count=3,
                departure_eta="02:20:00",
                arrival_eta="07:30:00",
                recon_duration="00:30:00",
            ),
            EchelonRowOut(
                echelon_id=2,
                echelon_label="2제대",
                ugv_count=3,
                departure_eta="02:10:00",
                arrival_eta="08:30:00",
                recon_duration="01:00:00",
            ),
            EchelonRowOut(
                echelon_id=3,
                echelon_label="3제대",
                ugv_count=3,
                departure_eta="02:30:00",
                arrival_eta="08:00:00",
                recon_duration="01:00:00",
            ),
        ]

        return CommanderEchelonsOut(run_id=run_id, rows=rows)
    
    async def get_commander_map(self, run_id: int, layer: str = "risk") -> CommanderMapOut | None:
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        remaining = await self.get_remaining_time(run_id)
        now = datetime.now().strftime("%Y.%m.%d %H:%M")

        # TODO: 실제 run_units / mission_targets / routes 테이블 연동
        markers = [
            CommanderMapMarkerOut(marker_type="start", label="출발지", lat=54.77, lon=18.41, echelon_id=None),
            CommanderMapMarkerOut(marker_type="target", label="정찰지1", lat=54.35, lon=19.87, echelon_id=1),
            CommanderMapMarkerOut(marker_type="target", label="정찰지2", lat=53.25, lon=20.50, echelon_id=2),
            CommanderMapMarkerOut(marker_type="target", label="정찰지3", lat=52.35, lon=20.90, echelon_id=3),
        ]

        routes = [
            CommanderRouteLineOut(
                route_id=1,
                echelon_id=1,
                label="1제대 경로",
                points=[[54.77, 18.41], [54.60, 18.90], [54.35, 19.87]],
                is_primary=True,
            ),
            CommanderRouteLineOut(
                route_id=2,
                echelon_id=2,
                label="2제대 경로",
                points=[[54.77, 18.41], [54.10, 19.30], [53.25, 20.50]],
                is_primary=True,
            ),
            CommanderRouteLineOut(
                route_id=3,
                echelon_id=3,
                label="3제대 경로",
                points=[[54.77, 18.41], [53.60, 19.80], [52.35, 20.90]],
                is_primary=True,
            ),
        ]

        overlay_url = None
        if layer == "risk":
            overlay_url = "/api/ltwr/maps/T0?kind=total"
        elif layer == "mobility":
            overlay_url = "/api/ltwr/maps/T0?kind=mobility"
        elif layer == "sensor":
            overlay_url = "/api/ltwr/maps/T0?kind=sensor"

        return CommanderMapOut(
            run_id=run_id,
            header=CommanderMapHeaderOut(
                current_time_label=now,
                remaining_time_label=remaining.remaining_hms if remaining else "02:00:34",
                selected_layer=layer,
                layer_tabs=["risk", "mobility", "sensor"],
            ),
            markers=markers,
            routes=routes,
            legend=["출발지", "도착지", "유인기", "UGV-1", "UGV-2", "UGV-3"],
            overlay_url=overlay_url,
        )
    
    async def get_commander_panels(self, run_id: int) -> CommanderPanelsOut | None:
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        latest = await self.latest_snapshot(run_id)

        queue_count = 0
        q = await self.get_sos_queue(run_id)
        if q:
            queue_count = q.danger_count

        active_alerts = []
        alerts = await self.get_alerts(run_id)
        if alerts:
            active_alerts = [a.message for a in alerts[:3] if a.message]

        return CommanderPanelsOut(
            run_id=run_id,
            mission_success_rate=latest.mission_success_rate if latest else None,
            mission_risk_rate=latest.asset_damage_rate if latest and latest.asset_damage_rate is not None else None,
            queue_count=queue_count,
            active_alerts=active_alerts,
        )
    async def get_commander_dashboard(self, run_id: int) -> CommanderDashboardOut | None:
        """GET /api/runs/{run_id}/commander/dashboard 통합 응답."""
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        now = datetime.now()
        latest = await self.latest_snapshot(run_id)
        remaining = await self.get_remaining_time(run_id)
        echelons_out = await self.get_commander_echelons(run_id)

        selected_mode = run.selected_mode or "balanced"
        mode_labels = {"balanced": "균형", "recon": "정찰", "rapid": "신속"}

        return CommanderDashboardOut(
            run_id=run_id,
            role_label="지휘관",
            current_time=now.strftime("%Y.%m.%d %H:%M"),
            remaining_time=remaining.remaining_hms if remaining else "00:00:00",
            selected_mode=selected_mode,
            mode_buttons=[
                CommanderModeItem(
                    key=k, label=v, selected=(k == selected_mode)
                )
                for k, v in mode_labels.items()
            ],
            metrics=CommanderMetricOut(
                success_rate=latest.mission_success_rate if latest else None,
                risk_rate=latest.asset_damage_rate if latest and latest.asset_damage_rate is not None else None,
            ),
            echelons=echelons_out.rows if echelons_out else [],
            map={
                "selected_layer": "risk",
                "layer_tabs": ["risk", "mobility", "sensor"],
                "overlay_url": "/api/ltwr/maps/T0?kind=total",
            },
            actions=CommanderActionState(
                execute_enabled=run.status in ("CREATED", "READY"),
                terminate_enabled=run.status == "RUNNING",
                dispatch_enabled=run.status in ("CREATED", "READY", "RUNNING"),
                replan_enabled=run.status == "RUNNING",
            ),
        )

    async def get_asset_status(
        self, run_id: int, user_role: str, user_scope: int | None = None
    ) -> AssetStatusListOut | None:
        """GET /api/runs/{run_id}/asset-status 전용.

        commander: 전체 제대 조회, operator: 본인 제대만.
        DB에 저장된 값이 없으면 mission_targets 기반 기본값 반환.
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        if mission is None:
            return None

        # 대상 제대 범위 결정
        if user_role == "commander":
            scopes = [1, 2, 3]
        else:
            scopes = [user_scope] if user_scope else [mission.echelon_no]

        items: list[AssetStatusItemOut] = []
        for scope in scopes:
            # DB에 저장된 최신 값 조회
            result = await self.db.execute(
                select(RunAssetStatus)
                .where(
                    RunAssetStatus.run_id == run_id,
                    RunAssetStatus.unit_scope == scope,
                )
                .order_by(RunAssetStatus.updated_at.desc())
                .limit(1)
            )
            saved = result.scalar_one_or_none()

            if saved:
                items.append(AssetStatusItemOut(
                    unit_scope=scope,
                    unit_label=f"{scope}제대",
                    troop_count=saved.troop_count,
                    operator_count=saved.operator_count,
                    sensor_count=saved.sensor_count,
                    available_ugv_count=saved.available_ugv_count,
                    target_count=saved.target_count,
                    departure_time=saved.departure_time,
                    arrival_time=saved.arrival_time,
                ))
            else:
                # 기본값: mission.total_ugv / targets 기반
                items.append(AssetStatusItemOut(
                    unit_scope=scope,
                    unit_label=f"{scope}제대",
                    available_ugv_count=mission.total_ugv,
                    target_count=1,
                ))

        # ── summary 계산 (전체 제대 합산) ──────────────────────
        total_controllers = sum(
            (i.operator_count or 0) for i in items
        )
        total_ugv = sum(
            (i.sensor_count or 0) for i in items
        )
        lost_ugv = sum(
            max(0, (i.sensor_count or 0) - (i.available_ugv_count or 0))
            for i in items
        )
        summary = AssetStatusSummaryOut(
            total_units=len(items),
            total_controllers=total_controllers,
            total_ugv=total_ugv,
            lost_ugv=lost_ugv,
        )

        return AssetStatusListOut(
            run_id=run_id,
            role=user_role,
            summary=summary,
            items=items,
        )

    async def patch_asset_status(
        self,
        run_id: int,
        user_id: int,
        user_role: str,
        user_scope: int | None,
        body: AssetStatusPatchIn,
    ) -> AssetStatusListOut | None:
        """PATCH /api/runs/{run_id}/asset-status 전용.

        commander: 모든 제대 수정 가능.
        operator: 본인 제대만 수정 가능.
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        for item in body.items:
            # operator 권한 제한
            if user_role != "commander" and item.unit_scope != user_scope:
                continue

            # 기존 레코드 조회 (upsert)
            result = await self.db.execute(
                select(RunAssetStatus)
                .where(
                    RunAssetStatus.run_id == run_id,
                    RunAssetStatus.unit_scope == item.unit_scope,
                )
                .order_by(RunAssetStatus.updated_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()

            if existing:
                if item.troop_count is not None:
                    existing.troop_count = item.troop_count
                if item.operator_count is not None:
                    existing.operator_count = item.operator_count
                if item.sensor_count is not None:
                    existing.sensor_count = item.sensor_count
                if item.available_ugv_count is not None:
                    existing.available_ugv_count = item.available_ugv_count
                if item.target_count is not None:
                    existing.target_count = item.target_count
                if item.departure_time is not None:
                    existing.departure_time = item.departure_time
                if item.arrival_time is not None:
                    existing.arrival_time = item.arrival_time
                existing.user_id = user_id
            else:
                new_rec = RunAssetStatus(
                    run_id=run_id,
                    user_id=user_id,
                    unit_scope=item.unit_scope,
                    troop_count=item.troop_count,
                    operator_count=item.operator_count,
                    sensor_count=item.sensor_count,
                    available_ugv_count=item.available_ugv_count,
                    target_count=item.target_count,
                    departure_time=item.departure_time,
                    arrival_time=item.arrival_time,
                )
                self.db.add(new_rec)

        await self.db.commit()
        return await self.get_asset_status(run_id, user_role, user_scope)

    async def dispatch_mission(self, run_id: int) -> DispatchResultOut | None:
        """POST /api/runs/{run_id}/dispatch 전용.

        run 상태를 DISPATCHED(또는 READY)로 전환, dispatched_at 기록.
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        now = datetime.now(timezone.utc)
        run.status = "READY"
        run.dispatched_at = now
        await self.db.commit()

        return DispatchResultOut(
            ok=True,
            run_id=run_id,
            message="임무 하달 완료",
            issued_at=now,
        )

    async def get_operator_briefing(
        self, run_id: int, echelon_no: int
    ) -> OperatorBriefingOut | None:
        """GET /api/runs/{run_id}/operator/briefing 전용 (PDF 8페이지)."""
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        mission = await self.db.get(Mission, run.mission_id)
        unit_label = f"{echelon_no}제대"

        asset_list = await self.get_asset_status(run_id, "operator", echelon_no)
        asset_item = asset_list.items[0] if asset_list and asset_list.items else None

        mode_labels = {"balanced": "균형형", "recon": "정찰형", "rapid": "신속형"}
        mode = run.selected_mode or "balanced"

        return OperatorBriefingOut(
            run_id=run_id,
            unit_label=unit_label,
            notice="임무를 하달받았습니다.",
            asset_status=asset_item,
            mission_info={
                "mode_label": mode_labels.get(mode, mode),
                "departure_eta": asset_item.departure_time.strftime("%H:%M:%S") if asset_item and asset_item.departure_time else "N/A",
                "arrival_eta": asset_item.arrival_time.strftime("%H:%M:%S") if asset_item and asset_item.arrival_time else "N/A",
            },
            map={
                "center_lat": mission.departure_lat if mission else 37.50,
                "center_lon": mission.departure_lon if mission else 127.00,
                "target_label": f"정찰지{echelon_no}",
            },
        )

    async def acknowledge_operator_briefing(
        self, run_id: int
    ) -> AcknowledgeResultOut | None:
        """POST /api/runs/{run_id}/operator/acknowledge 전용."""
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        now = datetime.now(timezone.utc)
        run.acknowledged_at = now
        await self.db.commit()

        return AcknowledgeResultOut(
            ok=True,
            run_id=run_id,
            message="임무 수령 확인 완료",
            acknowledged_at=now,
        )

    async def get_operator_dashboard(
        self, run_id: int, echelon_no: int
    ) -> OperatorDashboardOut | None:
        """GET /api/runs/{run_id}/operator/dashboard 전용 (PDF 9페이지).

        CommanderPage 기반 UserPage에 맞춰 확장:
          - tabs / selected_tab
          - metrics (success_rate, risk_rate)
          - echelons (자기 제대 1행만)
          - asset_panel (우측 패널 토글 메타)
        """
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        now = datetime.now()
        remaining = await self.get_remaining_time(run_id)
        latest = await self.latest_snapshot(run_id)
        asset_list = await self.get_asset_status(run_id, "operator", echelon_no)
        asset_item = asset_list.items[0] if asset_list and asset_list.items else None

        mode = run.selected_mode or "balanced"
        mode_labels = {"balanced": "균형", "recon": "정찰", "rapid": "신속"}
        unit_label = f"{echelon_no}제대"

        # ── 자기 제대 1행 (get_commander_echelons 데이터와 동일한 소스) ──
        echelons_out = await self.get_commander_echelons(run_id)
        my_echelon_rows = [
            row for row in (echelons_out.rows if echelons_out else [])
            if row.echelon_id == echelon_no
        ]

        # ── 자산 패널 메타 ──────────────────────────────────────────────
        asset_panel = OperatorAssetPanelOut(
            title="기본자산",
            tabs=["부대", unit_label],
            default_open=False,
        )

        return OperatorDashboardOut(
            run_id=run_id,
            role_label="통제관",
            tabs=["통제관", "자산 현황"],
            selected_tab="통제관",
            unit_label=unit_label,
            current_time=now.strftime("%Y.%m.%d %H:%M"),
            remaining_time=remaining.remaining_hms if remaining else "00:00:00",
            selected_mode={"key": mode, "label": mode_labels.get(mode, mode)},
            metrics=CommanderMetricOut(
                success_rate=latest.mission_success_rate if latest else None,
                risk_rate=(
                    latest.asset_damage_rate
                    if latest and latest.asset_damage_rate is not None
                    else None
                ),
            ),
            echelons=my_echelon_rows,
            actions=CommanderActionState(
                execute_enabled=run.status in ("READY", "RUNNING"),
                terminate_enabled=run.status == "RUNNING",
                dispatch_enabled=False,
                replan_enabled=run.status == "RUNNING",
            ),
            map={
                "selected_layer": "risk",
                "layer_tabs": ["risk", "mobility", "sensor"],
                "overlay_url": f"/api/ltwr/maps/T0?kind=total&echelon={echelon_no}",
            },
            asset_panel=asset_panel,
            asset_status=asset_item,
        )

    async def get_operator_map(
        self, run_id: int, echelon_no: int, layer: str = "risk"
    ) -> CommanderMapOut | None:
        """GET /api/runs/{run_id}/operator/map 전용.

        get_commander_map 결과를 자기 제대(echelon_no)로 필터링하여 반환.
        routes / markers 모두 자기 제대 관련 항목만 포함.
        """
        full_map = await self.get_commander_map(run_id, layer)
        if full_map is None:
            return None

        # 자기 제대 경로만 필터링
        my_routes = [r for r in full_map.routes if r.echelon_id == echelon_no]

        # 마커: echelon_id가 없는 공통 마커(출발지 등)는 포함, 다른 제대 마커는 제외
        my_markers = [
            m for m in full_map.markers
            if m.echelon_id is None or m.echelon_id == echelon_no
        ]

        return CommanderMapOut(
            run_id=run_id,
            header=full_map.header,
            markers=my_markers,
            routes=my_routes,
            legend=full_map.legend,
            overlay_url=f"/api/ltwr/maps/T0?kind=total&echelon={echelon_no}",
        )

    async def get_commander_setup(self, mission_id: int) -> CommanderSetupOut | None:
        """GET /api/missions/{mission_id}/commander-setup 전용 (PDF 3페이지)."""
        mission = await self.db.get(Mission, mission_id)
        if mission is None:
            return None

        targets_result = await self.db.execute(
            select(MissionTarget)
            .where(MissionTarget.mission_id == mission_id)
            .order_by(MissionTarget.seq.asc())
        )
        targets = list(targets_result.scalars().all())

        target_items = [
            CommanderSetupTargetItem(
                seq=t.seq,
                label=f"제대{t.seq}",
                lat=t.lat,
                lon=t.lon,
            )
            for t in targets
        ]

        # 지도 중심: 목표들의 중간값 또는 출발지
        if targets:
            center_lat = sum(t.lat for t in targets) / len(targets)
            center_lon = sum(t.lon for t in targets) / len(targets)
        else:
            center_lat = mission.departure_lat
            center_lon = mission.departure_lon

        rows = [
            CommanderSetupRowOut(
                echelon_id=t.seq,
                recon_target=t.seq,
                recon_time_sec=t.patrol_duration_sec,
            )
            for t in targets
        ]

        return CommanderSetupOut(
            mission_id=mission_id,
            map=CommanderSetupMapOut(
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=8,
                targets=target_items,
            ),
            rows=rows,
        )

    async def set_run_mode(self, run_id: int, mode: str) -> CommanderActionResultOut | None:
        """임무 모드 변경 (균형/정찰/신속)."""
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None
        valid_modes = {"balanced", "recon", "rapid"}
        if mode not in valid_modes:
            return None
        run.selected_mode = mode
        await self.db.commit()
        return CommanderActionResultOut(
            ok=True,
            action="set_mode",
            run_id=run_id,
            message=f"임무 모드 변경: {mode}",
            issued_at=datetime.now(timezone.utc),
        )

    async def get_sos_queue(self, run_id: int) -> SosQueueOut | None:
        return await self.get_danger_queue(run_id)

    async def commander_action(self, run_id: int, action: str) -> CommanderActionResultOut | None:
        run = await self.db.get(SimulationRun, run_id)
        if run is None:
            return None

        now = datetime.now(timezone.utc)

        if action == "execute":
            run.status = "RUNNING"
        elif action == "terminate":
            run.status = "CANCELLED"
        elif action == "dispatch":
            # 실제론 별도 command log 테이블 권장
            pass
        elif action == "replan-route":
            # 실제론 route_service / replan_engine 호출 권장
            pass

        await self.db.commit()
        await self.db.refresh(run)

        return CommanderActionResultOut(
            ok=True,
            action=action,
            run_id=run_id,
            message=f"{action} 처리 완료",
            issued_at=now,
        )
    