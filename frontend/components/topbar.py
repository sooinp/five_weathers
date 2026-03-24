## 상단 바 디자인 구성

import solara
from services.api_client import toggle_menu

@solara.component
def TopBar():
    with solara.Row(style={
        "align-items": "center",
        "padding": "10px",
        "background": "#dbeafe",
        "gap": "12px"
    }):
        solara.Button("☰", on_click=toggle_menu)
        solara.Markdown("## 악천후 MUM-T 의사결정지원 대시보드")