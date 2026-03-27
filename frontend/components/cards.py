## 우측 사이드 카드 디자인 구성
## 0327 기준 우측 패널의 카드/상세 오버레이 컴포넌트 모음

import solara
from services.api_client import close_unit_detail, open_unit_detail

def _badge_html(text: str, bg: str, fg: str = "#111827") -> str:
    # 아이덴티티 배지를 HTML 문자열로 만듦
    return (
        f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
        f'background:{bg};color:{fg};font-weight:700;font-size:12px;">{text}</span>'
    )

@solara.component
def UnitPriorityCard(unit: dict, is_selected: bool = False):
    # 선택된 제대는 테두리와 그림자를 더 강하게 주어 강조
    border = f"2px solid {unit['color']}" if is_selected else "1px solid #d1d5db"
    shadow = "0 10px 24px rgba(15,23,42,0.12)" if is_selected else "0 4px 12px rgba(15,23,42,0.08)"

    with solara.Card(
        style={
            "margin-bottom": "12px",
            "padding": "12px",
            "border": border,
            "box-shadow": shadow,
            "border-radius": "16px",
            "background": "white",
        }
    ):
        with solara.Row(style={"justify-content": "space-between", "align-items": "center"}):
            solara.Markdown(f"**{unit['name']}**")
            solara.HTML(tag="div", unsafe_innerHTML=_badge_html(unit["identity"], unit["color"], "white"))

        solara.Text(unit["summary"])
        with solara.Row(style={"gap": "8px", "margin-top": "10px", "flex-wrap": "wrap"}):
            # LTWR / SOS 버튼은 상세 오버레이를 여는 트리거 역할
            solara.Button(f"LTWR · {unit['ltwr']}", on_click=lambda: open_unit_detail("ltwr", unit["id"]))
            sos_label = "SOS · O" if unit["sos"] else "SOS · X"
            solara.Button(sos_label, on_click=lambda: open_unit_detail("sos", unit["id"]))

@solara.component
def DetailOverlay(detail: dict, unit: dict):
    # 상세 오버레이는 unit / detail 둘 중 하나라도 없으면 그리지 않음
    if not detail or not unit:
        return

    title = f"{unit['name']} LTWR" if detail["type"] == "ltwr" else f"{unit['name']} SOS"

    with solara.Card(
        style={
            # absolute 배치로 우측 패널 전체를 덮는 상세 레이어 만듦
            "position": "absolute",
            "top": "0",
            "left": "0",
            "right": "0",
            "bottom": "0",
            "z-index": "20",
            "padding": "16px",
            "background": "rgba(255,255,255,0.97)",
            "backdrop-filter": "blur(4px)",
            "overflow-y": "auto",
            "border-radius": "18px",
        }
    ):
        with solara.Row(style={"justify-content": "space-between", "align-items": "center"}):
            solara.Markdown(f"### {title}")
            solara.Button("✕", on_click=close_unit_detail)

        if detail["type"] == "ltwr":
            # LTWR 상세에서는 위험요인 TOP3를 막대 그래프로 표시
            solara.Text(f"현재 LTWR 등급: {unit['ltwr']}")
            solara.Text("위험요인 TOP3")
            for idx, driver in enumerate(unit["top3"], start=1):
                width = max(8, min(100, driver["value"]))
                bar_html = f'''
                <div style="margin:10px 0;">
                    <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:4px;">
                        <span>{idx}. {driver['name']}</span>
                        <span>{driver['value']}%</span>
                    </div>
                    <div style="width:100%;height:12px;background:#e5e7eb;border-radius:999px;overflow:hidden;">
                        <div style="width:{width}%;height:12px;background:{unit['color']};border-radius:999px;"></div>
                    </div>
                </div>
                '''
                solara.HTML(tag="div", unsafe_innerHTML=bar_html)
            solara.Text("설명: 상위 영향요인을 기준으로 현재 경로 유지 시 재계획 필요성을 판단할 수 있습니다.")
        else:
            # SOS 상세는 현재 경보를 구성한 관측 요소를 그대로 노출
            sos = unit["sos_detail"]
            solara.Text(f"대상 자산: {sos['asset']}")
            solara.Text(f"강수: {sos['rain']}")
            solara.Text(f"시정: {sos['visibility']}")
            solara.Text(f"토양수분: {sos['soil']}")
            solara.Text(f"지형: {sos['terrain']}")
            solara.Text(f"위험도: {sos['risk']}")
            solara.Text(sos['note'])
