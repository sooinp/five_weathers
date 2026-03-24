## 우측 사이드 카드 디자인 구성

import solara

@solara.component
def WarningCard(priority: int, title: str, content: str):
    with solara.Card(style={
        "margin-bottom": "10px",
        "padding": "8px"
    }):
        solara.Markdown(f"**[{priority}] {title}**")
        solara.Text(content)