## 상단 바 디자인 구성
## 0327 기준 현재 경로/ 성공 여부/ 임무 성공률/ 예상 비용이 작성되어 있음 -> 수정 예정

import solara

from services.api_client import (
    current_route_label,
    estimated_cost,
    mission_status,
    mission_success_rate,
    toggle_menu,
)


@solara.component
def TopBar():
    def kpi_box(label: str, value: str):
        with solara.Card(
            style={
                # 상단에 반복해서 쓰는 작은 KPI 카드
                "padding": "8px 12px",
                "min-width": "150px",
                "background": "white",
                "border-radius": "14px",
                "box-shadow": "0 2px 10px rgba(15,23,42,0.06)",
            }
        ):
            solara.Text(label)
            solara.Markdown(f"**{value}**")

    with solara.Column(
        style={
            # position/z-index를 주어 사이드 메뉴와 본문 위에서 헤더를 유지하는 역할
            "padding": "8px 12px 10px 12px",
            "background": "#f8fafc",
            "border-bottom": "1px solid #e5e7eb",
            "gap": "10px",
            "position": "relative",
            "z-index": "100",
        }
    ):
        with solara.Row(style={"align-items": "center", "gap": "10px"}):
            solara.Button("☰", on_click=toggle_menu)
            solara.Text("AI 기반 UGV 의사결정지원 시스템(?)")

        with solara.Row(
            style={
                "gap": "12px",
                "align-items": "stretch",
                "justify-content": "flex-start",
                "flex-wrap": "wrap",
            }
        ):
            kpi_box("현재 경로", current_route_label.value)
            kpi_box("성공 여부", mission_status.value)
            kpi_box("임무 성공률", f"{mission_success_rate.value}%")
            kpi_box("예상 비용", f"{estimated_cost.value} ₩")
