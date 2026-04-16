"""
backend/app/simulation/mock/dummy_runner.py

더미 시뮬레이션 실행기.

실제 알고리즘이 완성되기 전까지 서버-프론트 연동 검증을 위한
가짜 시뮬레이션. 진행률을 점진적으로 증가시키며
WebSocket으로 각종 이벤트를 push한다.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone

from app.db.models.patrol import RunPatrolEvent
from app.db.models.unit_state import RunQueueEvent, RunSosEvent, RunUnit
from app.db.models.route import RunKpi, RunMapLayer, RunRecommendation, RunRoute, RunRouteEffect
from app.db.models.snapshot import RunStatusSnapshot, RunTimeSeriesPanel
from app.db.session import AsyncSessionLocal
from app.core.websocket_manager import ws_manager
from app.simulation.contracts import WsEvent, make_event

logger = logging.getLogger(__name__)

TOTAL_STEPS = 10
STEP_SLEEP_SEC = 2.0


async def run_dummy(run_id: int) -> None:
    """
    더미 시뮬레이션 메인 루프.
    orchestrator.run_simulation()에서 호출.
    """
    logger.info("dummy_runner started run_id=%d", run_id)

    ugv_codes = [f"UGV-{run_id}-{i}" for i in range(1, 4)]

    # mission 기준 총 AOI 시간 조회
    aoi_total_sec: int = 1800  # 기본값 30분
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.db.models.simulation_run import SimulationRun as _Run
        from app.db.models.mission import Mission as _Mission
        _run = (await db.execute(select(_Run).where(_Run.id == run_id))).scalar_one_or_none()
        if _run:
            _mission = await db.get(_Mission, _run.mission_id)
            if _mission:
                aoi_total_sec = _mission.mission_duration_min * 60

    for step in range(1, TOTAL_STEPS + 1):
        await asyncio.sleep(STEP_SLEEP_SEC)
        progress = int(step / TOTAL_STEPS * 100)
        # 임무성공률: 0 ~ 100 (%) 범위 내
        success_rate = round(min(100.0, max(0.0, 50.0 + step * 3.0 + random.uniform(-2, 2))), 1)
        # 대기열 발생시간(구 자산피해율): -100 ~ 100 (%) 범위 내
        # 시뮬레이션 진행할수록 감소 (개선) 방향으로 더미값 생성
        damage_rate = round(max(-100.0, min(100.0, 15.0 - step * 1.5 + random.uniform(-2, 2))), 1)
        remaining = max(0, (TOTAL_STEPS - step) * int(STEP_SLEEP_SEC) * 30)
        # 정찰구역: 총 시간에서 진행 비율만큼 차감
        aoi_remaining = max(0, int(aoi_total_sec * (1 - step / TOTAL_STEPS)))

        async with AsyncSessionLocal() as db:
            # 1. 상태 스냅샷 저장
            snapshot = RunStatusSnapshot(
                run_id=run_id,
                status="RUNNING",
                phase="EXECUTION",
                progress_pct=progress,
                mission_success_rate=success_rate,
                asset_damage_rate=damage_rate,
                remaining_time_sec=remaining,
                aoi_remaining_sec=aoi_remaining,
                queue_length=random.randint(0, 2),
            )
            db.add(snapshot)

            # 2. 유닛 상태 업데이트
            from sqlalchemy import select
            for i, code in enumerate(ugv_codes):
                # step 3: UGV-0 → QUEUED 진입
                # step 5: UGV-1 → QUEUED 진입
                # step 4: UGV-1 → SOS
                # 나머지: MOVING / DONE
                prev_status = "STANDBY"
                if step < TOTAL_STEPS:
                    if step >= 3 and i == 0:
                        unit_status = "QUEUED"
                    elif step == 4 and i == 1:
                        unit_status = "SOS"
                    elif step >= 5 and i == 1:
                        unit_status = "QUEUED"
                    else:
                        unit_status = "MOVING"
                else:
                    unit_status = "DONE"

                lat = 37.5 + i * 0.01 + step * 0.001
                lon = 127.0 + i * 0.01 + step * 0.001

                result = await db.execute(
                    select(RunUnit).where(
                        RunUnit.run_id == run_id, RunUnit.unit_no == i + 1
                    )
                )
                unit = result.scalar_one_or_none()
                if unit is None:
                    unit = RunUnit(
                        run_id=run_id, unit_no=i + 1, asset_code=code,
                        status=unit_status, lat=lat, lon=lon,
                    )
                    db.add(unit)
                else:
                    prev_status = unit.status
                    unit.status = unit_status
                    unit.lat = lat
                    unit.lon = lon

                # 상태가 QUEUED로 전환될 때 ENTER 이벤트 기록
                if unit_status == "QUEUED" and prev_status != "QUEUED":
                    enter_evt = RunQueueEvent(
                        run_id=run_id,
                        asset_code=code,
                        event_type="ENTER",
                        wait_time_sec=random.randint(60, 300),
                        priority_score=round(random.uniform(0.7, 0.99), 2),
                    )
                    db.add(enter_evt)

                # QUEUED → 다른 상태로 전환 시 EXIT 이벤트 기록
                if prev_status == "QUEUED" and unit_status != "QUEUED":
                    exit_evt = RunQueueEvent(
                        run_id=run_id,
                        asset_code=code,
                        event_type="EXIT",
                        wait_time_sec=0,
                        priority_score=None,
                    )
                    db.add(exit_evt)

                # SOS 발생 시 RunSosEvent 생성 (대기열 카운트업 시작점)
                if unit_status == "SOS" and prev_status != "SOS":
                    sos_evt = RunSosEvent(
                        run_id=run_id,
                        unit_no=i + 1,
                        asset_code=code,
                        event_type="SOS",
                        sos_at=datetime.now(timezone.utc),
                        lat=lat,
                        lon=lon,
                    )
                    db.add(sos_evt)
                    await ws_manager.broadcast(run_id, make_event(WsEvent.ALERT_CREATED, run_id, {
                        "alert_type": "sos_triggered",
                        "unit_no": i + 1,
                        "asset_code": code,
                        "lat": lat,
                        "lon": lon,
                    }))

                # SOS → 다른 상태로 전환 시 resolved_at 기록 (일대일 처리 완료)
                if prev_status == "SOS" and unit_status != "SOS":
                    # 해당 unit의 미처리 SOS 이벤트 조회 후 resolved_at 업데이트
                    sos_result = await db.execute(
                        select(RunSosEvent).where(
                            RunSosEvent.run_id == run_id,
                            RunSosEvent.asset_code == code,
                            RunSosEvent.resolved_at.is_(None),
                        ).order_by(RunSosEvent.sos_at.asc()).limit(1)
                    )
                    pending_sos = sos_result.scalar_one_or_none()
                    if pending_sos:
                        pending_sos.resolved_at = datetime.now(timezone.utc)
                    await ws_manager.broadcast(run_id, make_event(WsEvent.QUEUE_UPDATED, run_id, {
                        "event": "sos_resolved",
                        "unit_no": i + 1,
                        "asset_code": code,
                    }))

                await ws_manager.broadcast(run_id, make_event(WsEvent.RUN_PROGRESS, run_id, {
                    "unit_no": i + 1,
                    "asset_code": code,
                    "status": unit_status,
                    "lat": lat,
                    "lon": lon,
                }))

            # 3. 대기열 이벤트 요약 (현재 QUEUED UGV 목록 broadcast)
            queued_codes = [
                ugv_codes[i] for i in range(len(ugv_codes))
                if (step >= 3 and i == 0) or (step >= 5 and i == 1)
            ]
            if queued_codes:
                queue_items = [
                    {"asset_code": c, "wait_time_sec": 120, "priority_score": 0.85}
                    for c in queued_codes
                ]
                # 더미 legacy 블록 유지 (짝수 step broadcast용)
            if step % 2 == 0 and queued_codes:
                evt = RunQueueEvent(
                    run_id=run_id,
                    asset_code=ugv_codes[0],
                    event_type="ENTER",
                    wait_time_sec=120,
                    priority_score=0.85,
                )
                db.add(evt)
                await ws_manager.broadcast(run_id, make_event(WsEvent.QUEUE_UPDATED, run_id, {
                    "queue_length": 1,
                    "items": queue_items,
                }))

            # 3-b. 정찰구역 이벤트 (UGV 목적지 도착 시뮬레이션)
            # step 3: UGV-1 → target_seq=1 도착
            # step 6: UGV-2 → target_seq=2 도착
            if step == 3:
                patrol_evt = RunPatrolEvent(
                    run_id=run_id,
                    unit_no=1,
                    asset_code=ugv_codes[0],
                    target_seq=1,
                    target_lat=37.51,
                    target_lon=127.01,
                    patrol_duration_sec=aoi_total_sec,
                    arrived_at=datetime.now(timezone.utc),
                )
                db.add(patrol_evt)
                await ws_manager.broadcast(run_id, make_event(WsEvent.ROUTE_UPDATED, run_id, {
                    "event": "patrol_arrived",
                    "unit_no": 1,
                    "asset_code": ugv_codes[0],
                    "target_seq": 1,
                    "patrol_duration_sec": aoi_total_sec,
                }))
            if step == 6:
                patrol_evt2 = RunPatrolEvent(
                    run_id=run_id,
                    unit_no=2,
                    asset_code=ugv_codes[1],
                    target_seq=2,
                    target_lat=37.52,
                    target_lon=127.02,
                    patrol_duration_sec=aoi_total_sec,
                    arrived_at=datetime.now(timezone.utc),
                )
                db.add(patrol_evt2)
                await ws_manager.broadcast(run_id, make_event(WsEvent.ROUTE_UPDATED, run_id, {
                    "event": "patrol_arrived",
                    "unit_no": 2,
                    "asset_code": ugv_codes[1],
                    "target_seq": 2,
                    "patrol_duration_sec": aoi_total_sec,
                }))

            # 4. 경로 저장 (step == 1)
            if step == 1:
                for i in range(len(ugv_codes)):
                    route = RunRoute(
                        run_id=run_id,
                        unit_no=i + 1,
                        route_type="INITIAL",
                        geojson={
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [127.0 + i * 0.01, 37.5 + i * 0.01],
                                    [127.1 + i * 0.01, 37.6 + i * 0.01],
                                ],
                            },
                            "properties": {"unit_no": i + 1},
                        },
                    )
                    db.add(route)

            # 5. 맵 레이어 3종 (RISK/MOBILITY/SENSOR)
            # step 2: RISK 레이어 (위험도)
            if step == 2:
                for slot in ["T0", "T1", "T2", "T3"]:
                    layer = RunMapLayer(
                        run_id=run_id,
                        layer_type="RISK",
                        time_slot=slot,
                        file_path=f"/data/risk_{slot}.tif",
                        meta={"dummy": True, "label": "위험도"},
                    )
                    db.add(layer)
                    await ws_manager.broadcast(run_id, make_event(WsEvent.LAYER_UPDATED, run_id, {
                        "layer_type": "RISK",
                        "time_slot": slot,
                    }))

            # step 3: MOBILITY 레이어 (기동성/토양수분)
            if step == 3:
                for slot in ["T0", "T1", "T2", "T3"]:
                    layer = RunMapLayer(
                        run_id=run_id,
                        layer_type="MOBILITY",
                        time_slot=slot,
                        file_path=f"/data/mobility_{slot}.tif",
                        meta={"dummy": True, "label": "기동성(토양수분)"},
                    )
                    db.add(layer)
                    await ws_manager.broadcast(run_id, make_event(WsEvent.LAYER_UPDATED, run_id, {
                        "layer_type": "MOBILITY",
                        "time_slot": slot,
                    }))

            # step 4: SENSOR 레이어 (센서/가시성)
            if step == 4:
                for slot in ["T0", "T1", "T2", "T3"]:
                    layer = RunMapLayer(
                        run_id=run_id,
                        layer_type="SENSOR",
                        time_slot=slot,
                        file_path=f"/data/sensor_{slot}.tif",
                        meta={"dummy": True, "label": "센서(가시성)"},
                    )
                    db.add(layer)
                    await ws_manager.broadcast(run_id, make_event(WsEvent.LAYER_UPDATED, run_id, {
                        "layer_type": "SENSOR",
                        "time_slot": slot,
                    }))

            # step 7: 환경 이벤트 발생 → 새 경로 제안 (replan_suggested)
            if step == 7:
                # 이벤트 종류 중 하나를 랜덤 선택 (기상악화 / 진창 / 통신두절)
                trigger = random.choice(["weather_degraded", "terrain_impassable", "comms_lost"])
                trigger_labels = {
                    "weather_degraded": "기상 급격히 악화",
                    "terrain_impassable": "진창(침수) 구역 발생",
                    "comms_lost": "통신 두절 구역 감지",
                }
                # 기존 경로와 다른 우회 경로 (더미 좌표)
                new_path_coords = [
                    [127.42, 37.45],
                    [127.44, 37.48],
                    [127.49, 37.51],
                    [127.53, 37.54],
                    [127.58, 37.55],
                ]
                await ws_manager.broadcast(run_id, make_event(WsEvent.ROUTE_UPDATED, run_id, {
                    "event": "replan_suggested",
                    "trigger": trigger,
                    "trigger_label": trigger_labels[trigger],
                    "unit_id": ugv_codes[0],
                    "path_geom": {
                        "type": "LineString",
                        "coordinates": new_path_coords,
                    },
                }))
                await ws_manager.broadcast(run_id, make_event(WsEvent.ALERT_CREATED, run_id, {
                    "alert_type": "replan_suggested",
                    "message": f"[경로 수정 제안] {trigger_labels[trigger]} — 새 경로가 제안되었습니다.",
                }))

            # step 5~8: LTWR 슬롯 순차 수신 (T0 → T1 → T2 → T3)
            # 실제 환경에서는 기상 예측 데이터가 시간대별로 순차 도착하는 것을 모사
            ltwr_slot_map = {5: "T0", 6: "T1", 7: "T2", 8: "T3"}
            if step in ltwr_slot_map:
                ltwr_slot = ltwr_slot_map[step]
                ltwr_layer = RunMapLayer(
                    run_id=run_id,
                    layer_type="LTWR",
                    time_slot=ltwr_slot,
                    file_path=f"/data/ltwr_{ltwr_slot}.tif",
                    meta={
                        "dummy": True,
                        "label": f"T+{step - 5}: {'Present Status' if step == 5 else 'Prediction'}",
                        "weather_type": "rainfall_probability",
                    },
                )
                db.add(ltwr_layer)
                await ws_manager.broadcast(run_id, make_event(WsEvent.LAYER_UPDATED, run_id, {
                    "layer_type": "LTWR",
                    "time_slot": ltwr_slot,
                }))

            # 6. T/T+1/T+2/T+3 패널 (매 step)
            for slot in ["T0", "T1", "T2", "T3"]:
                panel = RunTimeSeriesPanel(
                    run_id=run_id,
                    panel_type=slot,
                    data={
                        "success_rate": success_rate - random.uniform(0, 5),
                        "damage_rate": damage_rate + random.uniform(0, 3),
                        "step": step,
                    },
                )
                db.add(panel)

            await db.commit()

        # WebSocket run_status 브로드캐스트
        await ws_manager.broadcast(run_id, make_event(WsEvent.RUN_PROGRESS, run_id, {
            "status": "RUNNING",
            "phase": "EXECUTION",
            "progress_pct": progress,
            "mission_success_rate": success_rate,
            "asset_damage_rate": damage_rate,
            "remaining_time_sec": remaining,
            "aoi_remaining_sec": aoi_remaining,
            "queue_length": 0,
        }))

        logger.info("dummy step %d/%d run_id=%d progress=%d%%", step, TOTAL_STEPS, run_id, progress)

    # 완료 처리
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.db.models.simulation_run import SimulationRun
        result = await db.execute(select(SimulationRun).where(SimulationRun.id == run_id))
        run = result.scalar_one_or_none()
        if run and run.status == "RUNNING":
            run.status = "COMPLETED"
            run.progress_pct = 100
            run.finished_at = datetime.now(timezone.utc)

        # KPI 저장
        kpi = RunKpi(
            run_id=run_id,
            success_rate=round(50.0 + TOTAL_STEPS * 3.0, 1),
            damage_rate=5.0,
            makespan_sec=TOTAL_STEPS * int(STEP_SLEEP_SEC) * 30,
            queue_kpi={"avg_wait_sec": 90, "max_wait_sec": 180, "total_events": 5},
            bottleneck_index=0.2,
        )
        db.add(kpi)

        # 현재경로 효과 더미 (최적경로 vs 차선책 delta)
        optimal_sr = round(50.0 + TOTAL_STEPS * 3.0, 1)   # 최적경로 임무성공률
        alt_sr     = round(optimal_sr - 12.0, 1)           # 차선책 임무성공률 (12%p 낮음)
        optimal_dr = 5.0                                    # 최적경로 대기열 발생시간
        alt_dr     = round(optimal_dr + 7.0, 1)            # 차선책 대기열 발생시간 (7%p 높음)
        route_effect = RunRouteEffect(
            run_id=run_id,
            optimal_success_rate=optimal_sr,
            optimal_damage_rate=optimal_dr,
            alt_success_rate=alt_sr,
            alt_damage_rate=alt_dr,
            success_rate_delta=round(optimal_sr - alt_sr, 1),   # +12.0
            damage_rate_delta=round(optimal_dr - alt_dr, 1),    # -7.0
        )
        db.add(route_effect)

        # 추천 결과 더미
        rec = RunRecommendation(
            run_id=run_id,
            score=0.87,
            is_selected=True,
            rationale={"reason": "highest_success_rate", "dummy": True},
        )
        db.add(rec)

        await db.commit()

    await ws_manager.broadcast(run_id, make_event(WsEvent.RUN_FINISHED, run_id, {
        "status": "COMPLETED",
        "phase": "DONE",
        "progress_pct": 100,
        "mission_success_rate": round(50.0 + TOTAL_STEPS * 3.0, 1),
        "asset_damage_rate": 5.0,
        "remaining_time_sec": 0,
        "queue_length": 0,
    }))

    logger.info("dummy_runner completed run_id=%d", run_id)
