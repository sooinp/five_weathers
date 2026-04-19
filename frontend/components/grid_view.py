"""
frontend/components/grid_view.py

── 팀원 코드: 중앙 전술 맵 컴포넌트 (시간 표시 + 자동 경로수정 토글 추가) ──
원본: C:/Users/sooin/Documents/카카오톡 받은 파일/frontend_fixed/frontend/components/grid_view.py

역할:
- 위험도 / 기동성 / 센서 레이어 탭 전환
- 맵 본체 렌더링
- 현재 시각 + 남은 시간 패널 (map-time-panel)
- 범례 + 경로 수정 버튼 (5초 활성 / 10초 비활성 자동 토글)
"""

import solara
import solara.lab
import time
import asyncio

from services.api_client import (
    BACKEND_HTTP_BASE,
    map_selection,
    set_map_selection,
    ratio_x,
    UGV_ICONS,
    replan_available,
    request_replan,
)

from components.state import (
    timer_running,
    timer_end_ts,
    remaining_time_text_global,
    timer_remaining_secs,
    video_should_play,
)


# ── 팀원 코드: 시간 표시 + 자동 토글 GridView ─────────────────────────────
@solara.component
def GridView():
    # 팀원 코드: 5초 활성 / 10초 비활성 자동 토글 상태
    is_active = solara.use_reactive(False)
    last_toggle_time = solara.use_reactive(time.time())

    # 팀원 코드: 시간 표시 상태
    current_time_text = solara.use_reactive(time.strftime("%Y.%m.%d %H:%M"))
    remaining_display = solara.use_reactive(remaining_time_text_global.value)

    # 백엔드 상태 (비동기로 체크 — 렌더 블로킹 없음)
    backend_alive   = solara.use_reactive(True)
    sim_available   = solara.use_reactive(False)
    video_available = solara.use_reactive(False)  # MP4 영상 사용 가능 여부

    # 팀원 코드: 경로 수정 버튼 자동 토글 루프 (5초 on / 10초 off)
    @solara.lab.use_task
    async def button_control_loop():
        while True:
            await asyncio.sleep(0.5)
            current_now = time.time()
            elapsed = current_now - last_toggle_time.value

            if is_active.value:
                if elapsed >= 5.0:
                    is_active.value = False
                    last_toggle_time.value = current_now
            else:
                if elapsed >= 10.0:
                    is_active.value = True
                    last_toggle_time.value = current_now

    # 임무 타이머 카운트다운 (0.5초마다 10분 감산 — 7초=14틱에 02:20:00→00:00:00)
    @solara.lab.use_task
    async def clock_loop():
        while True:
            if timer_running.value and timer_end_ts.value is not None:
                secs = timer_remaining_secs.value - 600  # 10분 감산
                if secs <= 0:
                    remaining_time_text_global.value = "00:00:00"
                    remaining_display.value = "00:00:00"
                    timer_running.value = False
                    timer_end_ts.value = None
                    timer_remaining_secs.value = 0
                else:
                    timer_remaining_secs.value = secs
                    h = secs // 3600
                    m = (secs % 3600) // 60
                    txt = f"{h:02d}:{m:02d}:00"
                    remaining_time_text_global.value = txt
                    remaining_display.value = txt

            await asyncio.sleep(0.5)

    # 백엔드 헬스체크 + sim/video status — 5초마다 비동기로 확인 (렌더 블로킹 없음)
    @solara.lab.use_task
    async def health_check_loop():
        import requests as _hreq
        def _check():
            try:
                _hreq.get(f"{BACKEND_HTTP_BASE}/health", timeout=2)
                alive = True
            except Exception:
                alive = False
            sim = False
            video = False
            if alive:
                try:
                    r = _hreq.get(
                        f"{BACKEND_HTTP_BASE}/api/map/video/status", timeout=2
                    ).json()
                    video = r.get("available", False)
                except Exception:
                    video = False
                try:
                    r = _hreq.get(
                        f"{BACKEND_HTTP_BASE}/api/map/sim/status", timeout=2
                    ).json()
                    sim = r.get("available", False)
                except Exception:
                    sim = False
            return alive, sim, video
        while True:
            _alive, _sim, _video = await asyncio.to_thread(_check)
            backend_alive.value   = _alive
            sim_available.value   = _sim
            video_available.value = _video
            await asyncio.sleep(5)

    def handle_replan_click():
        if is_active.value:
            request_replan()
            is_active.value = False
            last_toggle_time.value = time.time()

    solara.Style("""
        .gridview-root {
            width: 100%;
            height: 100%;
            min-height: 0;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-sizing: border-box;
            background: transparent !important;
        }

        .map-top-controls {
            background: transparent !important;
            display: flex;
            justify-content: flex-start;
            align-items: center;
            gap: 10px;
            flex: 0 0 auto;
            margin-bottom: 8px;
        }

        .map-main-display {
            flex: 1 1 auto;
            min-height: 0;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px dashed rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            margin-bottom: 8px;
            overflow: hidden;
            box-sizing: border-box;
            background-color: rgba(15, 23, 38, 0.38) !important;
        }

        .map-bottom-bar {
            background: transparent !important;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            flex: 0 0 auto;
            width: 100%;
            min-width: 0;
            color: #cbd5e1 !important;
        }

        .map-legend-bar {
            background: transparent !important;
            display: flex;
            align-items: center;
            gap: 18px;
            flex: 1 1 auto;
            min-width: 0;
            overflow-x: auto;
            overflow-y: hidden;
            white-space: nowrap;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: #cbd5e1;
            flex-shrink: 0;
        }

        .action-btn {
            height: 34px !important;
            width: 82px !important;
            font-size: 14px !important;
            font-weight: bold !important;
            border-radius: 6px !important;
            padding: 0 !important;
        }

        .btn-active {
            background-color: #e67e22 !important;
            color: white !important;
            opacity: 1.0 !important;
        }

        .btn-default {
            background-color: #2d3a54 !important;
            color: white !important;
            opacity: 0.8 !important;
        }

        .replan-btn {
            min-width: 110px !important;
            max-width: 110px !important;
            height: 34px !important;
            font-size: 14px !important;
            font-weight: bold !important;
            border-radius: 6px !important;
            flex-shrink: 0;
            transition: all 0.3s ease;
        }

        .gridview-root > div,
        .gridview-root .v-sheet,
        .map-main-display > div,
        .map-main-display .v-sheet {
            background: transparent !important;
            box-shadow: none !important;
        }

        /* 팀원 코드: 맵 영역 내 시간 패널 */
        .map-main-display {
            position: relative;
            flex: 1 1 auto;
            min-height: 0;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px dashed rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            margin-bottom: 8px;
            overflow: hidden;
            box-sizing: border-box;
            background-color: rgba(15, 23, 38, 0.38) !important;
        }

        .map-time-panel {
            position: absolute;
            top: 12px;
            right: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 20;
            align-items: flex-end;
        }

        .time-chip {
            min-width: 190px;
            height: 38px;
            padding: 0 16px;
            border-radius: 8px;
            background: rgba(37, 52, 82, 0.35);
            border: 1px solid rgba(148, 163, 184, 0.12);
            color: white;
            font-size: 15px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            white-space: nowrap;
        }
    """)

    # 레이아웃
    with solara.Div(classes=["gridview-root"]):

        # 1) 상단 탭 줄
        with solara.Div(classes=["map-top-controls"]):
            for m in ["종합상황도", "기동기반", "센서기반"]:
                solara.Button(
                    m,
                    on_click=lambda x=m: set_map_selection(x),
                    classes=[
                        "action-btn",
                        "btn-active" if map_selection.value == m else "btn-default",
                    ],
                )

        # 2) 중앙 맵 영역 (팀원 코드: 시간 패널 포함)
        with solara.Div(classes=["map-main-display"]):
            with solara.Div(classes=["map-time-panel"]):
                with solara.Div(classes=["time-chip"]):
                    solara.Text(f"남은 시간 {remaining_display.value}")

            # 우선순위: 영상(MP4) > 시뮬 HTML > 그리드 맵 > 대기 화면
            # (video_available, sim_available, backend_alive 는 use_task로 비동기 체크)
            if video_available.value:
                # 1순위: 시뮬레이션 결과 MP4 영상 (player.html 직접 서빙)
                # ?play=1 → 즉시 재생, ?play=0 → 첫 프레임 정지
                _play_param = "1" if video_should_play.value else "0"
                solara.HTML(
                    tag="iframe",
                    attributes={
                        "src": f"{BACKEND_HTTP_BASE}/sim-videos/player.html?play={_play_param}",
                        "style": "position:absolute; top:0; left:0; width:100%; height:100%; border:none;",
                        "allow": "autoplay",
                    },
                )
            elif sim_available.value:
                # 2순위: 시뮬레이션 결과 HTML 맵
                solara.HTML(
                    tag="iframe",
                    attributes={
                        "src": f"{BACKEND_HTTP_BASE}/sim-maps/current.html",
                        "style": "position:absolute; top:0; left:0; width:100%; height:100%; border:none;",
                    },
                )
            elif backend_alive.value:
                # 백엔드 살아있음 → 그리드 맵
                _layer_key = {"종합상황도": "risk", "기동기반": "mobility", "센서기반": "sensor"}.get(
                    map_selection.value, "risk"
                )
                solara.HTML(
                    tag="iframe",
                    attributes={
                        "src": f"{BACKEND_HTTP_BASE}/api/map/grid/html?layer={_layer_key}",
                        "style": "position:absolute; top:0; left:0; width:100%; height:100%; border:none;",
                    },
                )
            else:
                # 백엔드 꺼짐 → 인라인 대기 화면 (외부 서버 불필요)
                _placeholder = "\n".join([
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
                    "*{margin:0;padding:0;box-sizing:border-box}",
                    "body{width:100vw;height:100vh;background:#0f1726;",
                    "display:flex;flex-direction:column;",
                    "align-items:center;justify-content:center;gap:18px}",
                    ".icon{font-size:48px;opacity:0.35}",
                    ".msg{color:#94a3b8;font-size:15px;font-family:sans-serif}",
                    ".sub{color:#475569;font-size:12px;font-family:sans-serif}",
                    "</style></head><body>",
                    "<div class='icon'>\U0001f5fa\ufe0f</div>",
                    "<div class='msg'>맵 데이터 대기 중...</div>",
                    "<div class='sub'>시뮬레이션 결과가 수신되면 자동으로 표시됩니다.</div>",
                    "</body></html>",
                ])
                solara.HTML(
                    tag="iframe",
                    attributes={
                        "srcdoc": _placeholder,
                        "style": "position:absolute; top:0; left:0; width:100%; height:100%; border:none;",
                    },
                )

        # 3) 하단 범례 + 경로 수정 버튼
        with solara.Div(classes=["map-bottom-bar"]):
            with solara.Div(classes=["map-legend-bar"]):
                with solara.Div(classes=["legend-item"]):
                    solara.HTML(
                        tag="div",
                        unsafe_innerHTML=(
                            '<svg width="18" height="22" viewBox="0 0 24 24" fill="none">'
                            '<path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2Z" fill="#10B981"/>'
                            '<circle cx="12" cy="9" r="3" fill="white"/></svg>'
                        ),
                    )
                    solara.Text("출발지")

                with solara.Div(classes=["legend-item"]):
                    solara.HTML(
                        tag="div",
                        unsafe_innerHTML=(
                            '<svg width="18" height="22" viewBox="0 0 24 24" fill="none">'
                            '<path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2Z" fill="#FF0000"/>'
                            '<circle cx="12" cy="9" r="3" fill="white"/></svg>'
                        ),
                    )
                    solara.Text("도착지")

                with solara.Div(classes=["legend-item"]):
                    solara.Text("●", style={"color": "#cbd5e1", "font-size": "14px"})
                    solara.Text("통제관")

                num_ugvs = min(max(int(ratio_x.value), 0), 4)
                for i in range(1, num_ugvs + 1):
                    icon = UGV_ICONS.get(i, "●")
                    with solara.Div(classes=["legend-item"]):
                        solara.Text(icon, style={"font-size": "14px"})
                        solara.Text(f"UGV-{i}")

            solara.Button(
                "경로 수정",
                on_click=handle_replan_click,
                disabled=not is_active.value,
                classes=["replan-btn"],
                style={
                    "background-color": "#e67e22" if is_active.value else "#374151",
                    "color": "white" if is_active.value else "#94a3b8",
                    "border": "none",
                    "opacity": "1",
                    "cursor": "pointer" if is_active.value else "default",
                },
            )
