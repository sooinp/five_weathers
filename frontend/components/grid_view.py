## 격자 시각화
## 0320 기준 자리 표시용 컴포넌트
## 0327 기준 지형(terrain)을 베이스로 그리고, 선택된 탭(위험도/강수/시정/토양수분) 오버레이.
##          + 제대별 경로, 시작/도착점, UGV 위치 틱별로 렌더링

import solara

from services.api_client import (
    map_selection,
    set_map_selection,
    ratio_x,
    UGV_ICONS,
    replan_available,
    request_replan,
)


@solara.component
def GridView():
    solara.Style("""
        .map-top-controls {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            flex-shrink: 0;
        }

        .map-main-display {
            flex: 1 1 auto;
            min-height: 420px;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px dashed rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            margin-bottom: 10px;
            overflow: hidden;
            box-sizing: border-box;
        }

        .map-bottom-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            flex-shrink: 0;
            width: 100%;
        }

        .map-legend-bar {
            flex: 1 1 auto;
            min-width: 0;
            overflow-x: auto;
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
            height: 38px !important;
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
            flex-shrink: 0;
        }
    """)

    with solara.Column(classes=["center-map-area"]):
        with solara.Row(classes=["map-top-controls"]):
            for m in ["위험도", "기동성", "센서"]:
                solara.Button(
                    m,
                    on_click=lambda x=m: set_map_selection(x),
                    classes=[
                        "action-btn",
                        "btn-active" if map_selection.value == m else "btn-default",
                    ],
                )

        with solara.Div(classes=["map-main-display"]):
            # 나중에 실제 맵 렌더링 코드가 들어갈 자리
            solara.Text(
                f"{map_selection.value} 맵 데이터 수신 중...",
                style={
                    "color": "#94a3b8",
                    "font-weight": "bold",
                    "font-size": "20px",
                },
            )

        with solara.Row(classes=["map-bottom-bar"]):
            with solara.Row(classes=["map-legend-bar"]):
                with solara.Div(classes=["legend-item"]):
                    solara.Text("🚩 출발지")
                with solara.Div(classes=["legend-item"]):
                    solara.Text("⭐ 도착지")
                with solara.Div(classes=["legend-item"]):
                    solara.Text("● 유인기")

                num_ugvs = min(max(int(ratio_x.value), 0), 4)
                for i in range(1, num_ugvs + 1):
                    icon = UGV_ICONS.get(i, "●")
                    with solara.Div(classes=["legend-item"]):
                        solara.Text(f"{icon} UGV-{i}")

            solara.Button(
                "경로 수정",
                on_click=request_replan,
                disabled=not replan_available.value,
                classes=["replan-btn"],
                style={
                    "background-color": "#e67e22" if replan_available.value else "#6b7280",
                    "color": "white",
                    "opacity": "1" if replan_available.value else "0.5",
                },
            )