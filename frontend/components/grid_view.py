## 격자 시각화
## 0320 기준 자리 표시용 컴포넌트

import solara
from services.api_client import (
    risk_grid,
    planned_path,
    start_point,
    end_point,
    ugv_positions,
)

def cell_color(value: int) -> str:
    if value == 0:
        return "#f8fafc"   # 일반
    elif value == 1:
        return "#fde68a"   # 주의
    elif value == 2:
        return "#fca5a5"   # 위험
    return "#e5e7eb"

@solara.component
def GridView():
    grid = risk_grid.value
    path = planned_path.value
    start = start_point.value
    end = end_point.value
    ugvs = ugv_positions.value

    if not grid or not grid[0]:
        with solara.Column():
            solara.Text("시뮬레이션 맵 / 그리드 영역")
            solara.Div(
                style={
                    "width": "100%",
                    "height": "420px",
                    "border": "2px solid #ef4444",
                    "background": "#f8fafc",
                    "display": "flex",
                    "align-items": "center",
                    "justify-content": "center",
                    "font-size": "18px"
                },
                children=["시뮬레이션 실행 전입니다."]
            )
        return

    rows = len(grid)
    cols = len(grid[0])

    cell_size = 32
    width = cols * cell_size
    height = rows * cell_size

    path_points = []
    for r, c in path:
        x = c * cell_size + cell_size / 2
        y = r * cell_size + cell_size / 2
        path_points.append(f"{x},{y}")
    polyline_points = " ".join(path_points)

    svg_parts = []

    # 셀 그리기
    for r in range(rows):
        for c in range(cols):
            x = c * cell_size
            y = r * cell_size
            fill = cell_color(grid[r][c])

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{fill}" stroke="#cbd5e1" stroke-width="1" />'
            )

    # 경로 그리기
    if polyline_points:
        svg_parts.append(
            f'<polyline points="{polyline_points}" '
            f'fill="none" stroke="#2563eb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />'
        )

    # 시작점
    if start:
        sr, sc = start
        sx = sc * cell_size + cell_size / 2
        sy = sr * cell_size + cell_size / 2
        svg_parts.append(
            f'<circle cx="{sx}" cy="{sy}" r="10" fill="#16a34a" />'
            f'<text x="{sx}" y="{sy + 4}" text-anchor="middle" font-size="10" fill="white">S</text>'
        )

    # 도착점
    if end:
        er, ec = end
        ex = ec * cell_size + cell_size / 2
        ey = er * cell_size + cell_size / 2
        svg_parts.append(
            f'<circle cx="{ex}" cy="{ey}" r="10" fill="#dc2626" />'
            f'<text x="{ex}" y="{ey + 4}" text-anchor="middle" font-size="10" fill="white">E</text>'
        )

    # UGV 위치
    for idx, (r, c) in enumerate(ugvs):
        ux = c * cell_size + cell_size / 2
        uy = r * cell_size + cell_size / 2
        svg_parts.append(
            f'<rect x="{ux - 7}" y="{uy - 7}" width="14" height="14" fill="#111827" rx="2" />'
            f'<text x="{ux}" y="{uy + 4}" text-anchor="middle" font-size="8" fill="white">{idx + 1}</text>'
        )

    svg_content = "".join(svg_parts)
    svg_html = f"""
    <div style="width: 100%; overflow: auto; border: 2px solid #ef4444; background: white; padding: 8px;">
        <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
            {svg_content}
        </svg>
    </div>
    """

    with solara.Column():
        solara.Markdown("#### 격자 지도")
        solara.HTML(tag="div", unsafe_innerHTML=svg_html)

        with solara.Row(style={"gap": "12px", "margin-top": "8px"}):
            solara.Text("🟩 시작점")
            solara.Text("🟥 도착점")
            solara.Text("🟨 주의 셀")
            solara.Text("🟥 위험 셀")
            solara.Text("🟦 경로")
            solara.Text("⬛ UGV")