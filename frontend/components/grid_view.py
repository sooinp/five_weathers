## 격자 시각화
## 0320 기준 자리 표시용 컴포넌트
## 0327 기준 지형(terrain)을 베이스로 그리고, 선택된 탭(위험도/강수/시정/토양수분) 오버레이.
##          + 제대별 경로, 시작/도착점, UGV 위치 틱별로 렌더링

import html
import solara
from services.api_client import (
    current_map_tab,
    end_point,
    get_selected_unit,
    rain_grid,
    risk_grid,
    soil_grid,
    start_point,
    terrain_grid,
    units_data,
    visibility_grid,
)


def terrain_color(value: int) -> str:
    if value == 1:
        return "#efe6c8"   # 일반
    if value == 2:
        return "#ddd6c1"   # 주의
    if value == 3:
        return "#cbd5e1"   # 위험
    return "#f8fafc"


def overlay_color(value: int, tab: str) -> str:
    if value == 0:
        return "transparent"
    palette = {
        "rain": {1: "rgba(59,130,246,0.28)", 2: "rgba(37,99,235,0.48)"},
        "visibility": {1: "rgba(148,163,184,0.26)", 2: "rgba(100,116,139,0.48)"},
        "soil": {1: "rgba(180,83,9,0.24)", 2: "rgba(120,53,15,0.42)"},
        "risk": {1: "rgba(251,191,36,0.35)", 2: "rgba(239,68,68,0.40)"},
    }
    return palette.get(tab, palette["risk"]).get(value, "transparent")

# 현재 탭에 대응하는 2차원 격자 데이터를 반환
def active_layer_grid() -> list[list[int]]:
    tab = current_map_tab.value
    if tab == "rain":
        return rain_grid.value
    if tab == "visibility":
        return visibility_grid.value
    if tab == "soil":
        return soil_grid.value
    return risk_grid.value

# 버튼에 표시할 맵 레이어 목록
MAP_TABS = [
    ("risk", "위험도"),
    ("rain", "강수"),
    ("visibility", "시정"),
    ("soil", "토양수분"),
]


@solara.component
def GridView():
    terrain = terrain_grid.value
    overlay = active_layer_grid()
    units = units_data.value
    selected = get_selected_unit()
    start = start_point.value
    end = end_point.value

    # 스냅샷을 아직 받지 못한 경우 빈 상태 화면을 먼저 보여줌
    if not terrain or not terrain[0]:
        with solara.Column():
            solara.Markdown("#### 전술 격자 지도")
            solara.Div(
                style={
                    "width": "100%",
                    "height": "420px",
                    "border": "1px solid #cbd5e1",
                    "background": "#f8fafc",
                    "display": "flex",
                    "align-items": "center",
                    "justify-content": "center",
                    "font-size": "18px",
                    "border-radius": "18px",
                },
                children=["시뮬레이션 실행 전입니다."],
            )
        return

    rows = len(terrain)
    cols = len(terrain[0])
    cell_size = 32
    width = cols * cell_size
    height = rows * cell_size
    svg_parts = []

    # 셀 그리기
    for r in range(rows):
        for c in range(cols):
            x = c * cell_size
            y = r * cell_size
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{terrain_color(terrain[r][c])}" stroke="#dbe2ea" stroke-width="1" rx="5" />'
            )
            overlay_fill = overlay_color(overlay[r][c], current_map_tab.value)
            if overlay_fill != "transparent":
                svg_parts.append(
                    f'<rect x="{x + 1.5}" y="{y + 1.5}" width="{cell_size - 3}" height="{cell_size - 3}" '
                    f'fill="{overlay_fill}" rx="5" />'
                )

    # 셀 그리기(terrain = 3일 때 - 선 추가)
    for r in range(rows):
        for c in range(cols):
            if terrain[r][c] == 3:
                x1 = c * cell_size + 6
                y1 = r * cell_size + cell_size / 2
                x2 = c * cell_size + cell_size - 6
                y2 = y1
                svg_parts.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#94a3b8" stroke-width="2" opacity="0.7" />'
                )

    # 경로 그리기
    for unit in units:
        points = " ".join(
            f"{c * cell_size + cell_size / 2},{r * cell_size + cell_size / 2}" for r, c in unit["path"]
        )
        selected_now = selected and unit["id"] == selected["id"]
        opacity = "0.95" if selected_now else "0.28"
        width_px = "6" if selected_now else "3"
        svg_parts.append(
            f'<polyline points="{points}" fill="none" stroke="{unit["color"]}" '
            f'stroke-width="{width_px}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round" />'
        )
        # 지금 보고 있는 대상 강조
        if selected_now:
            for r, c in unit["path"]:
                x = c * cell_size + 4
                y = r * cell_size + 4
                svg_parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell_size - 8}" height="{cell_size - 8}" '
                    f'fill="none" stroke="{unit["color"]}" stroke-width="2.5" rx="8" opacity="0.9" />'
                )

    # 시작점 마커
    if start:
        sr, sc = start
        sx = sc * cell_size + cell_size / 2
        sy = sr * cell_size + cell_size / 2
        svg_parts.append(f'<circle cx="{sx}" cy="{sy}" r="11" fill="#16a34a" />')
        svg_parts.append(f'<text x="{sx}" y="{sy + 4}" text-anchor="middle" font-size="10" fill="white">S</text>')

    # 도착점 마커
    if end:
        er, ec = end
        ex = ec * cell_size + cell_size / 2
        ey = er * cell_size + cell_size / 2
        svg_parts.append(f'<circle cx="{ex}" cy="{ey}" r="11" fill="#dc2626" />')
        svg_parts.append(f'<text x="{ex}" y="{ey + 4}" text-anchor="middle" font-size="10" fill="white">E</text>')

    # UGV 위치 아이콘 표
    for unit in units:
        selected_now = selected and unit["id"] == selected["id"]
        for index, ugv in enumerate(unit["ugvs"], start=1):
            r, c = ugv["pos"]
            ux = c * cell_size + cell_size / 2
            uy = r * cell_size + cell_size / 2
            stroke = "#111827" if selected_now else "#ffffff"
            stroke_width = "3" if selected_now else "1.2"
            svg_parts.append(
                f'<circle cx="{ux}" cy="{uy}" r="9" fill="{unit["color"]}" stroke="{stroke}" stroke-width="{stroke_width}" />'
            )
            svg_parts.append(
                f'<text x="{ux}" y="{uy + 3.5}" text-anchor="middle" font-size="7" fill="white">{index}</text>'
            )

    # 우측 카드에서 선택한 제대가 있으면, 맵 상단에 현재 강조 상태 배너
    banner_html = ""
    if selected:
        tab_title = dict(MAP_TABS).get(current_map_tab.value, "위험도")
        banner_html = (
            f'<div style="max-width:440px;padding:10px 12px;border-radius:14px;'
            f'background:rgba(255,255,255,0.96);border:1px solid #e2e8f0;box-shadow:0 6px 16px rgba(15,23,42,0.08);">'
            f'<div style="font-weight:700;color:{selected["color"]};margin-bottom:4px;">{html.escape(selected["name"])} 강조 표시 중</div>'
            f'<div style="font-size:13px;color:#334155;">현재 레이어: {tab_title} · {html.escape(selected["summary"])} </div>'
            f'</div>'
        )

    svg_html = f'''
    <div style="width:100%;overflow:auto;border:1px solid #dbe2ea;background:white;padding:10px;border-radius:18px;">
        <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
            {''.join(svg_parts)}
        </svg>
    </div>
    '''

    with solara.Column():
        # 상단은 레이어 탭, 우측은 선택 배너
        with solara.Row(
            style={
                "gap": "12px",
                "margin-bottom": "10px",
                "align-items": "flex-start",
                "justify-content": "space-between",
                "flex-wrap": "wrap",
            }
        ):
            with solara.Row(style={"gap": "8px", "flex-wrap": "wrap"}):
                for key, label in MAP_TABS:
                    is_active = current_map_tab.value == key
                    solara.Button(
                        label,
                        on_click=lambda key=key: setattr(current_map_tab, "value", key),
                        color="primary" if is_active else None,
                        text=not is_active,
                    )
            if banner_html:
                solara.HTML(tag="div", unsafe_innerHTML=banner_html)

        solara.HTML(tag="div", unsafe_innerHTML=svg_html)
        # 범례 - 맵 요소 표시됨
        with solara.Row(style={"gap": "14px", "margin-top": "8px", "flex-wrap": "wrap"}):
            solara.Text("공통 지형 = 베이스 셀")
            solara.Text("🟩 시작점")
            solara.Text("🟥 도착점")
            solara.Text("색상 경로 = 제대 경로")
            solara.Text("원형 아이콘 = UGV")
            solara.Text("탭별 오버레이 = 강수 / 시정 / 토양수분 / 미션 위험도")
