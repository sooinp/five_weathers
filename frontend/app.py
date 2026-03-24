## Solara 메인

import solara

from components.topbar import TopBar
from components.sidebar import SideMenu
from components.pages import MainPage, LoginPage, SignupPage, MyPage
from services.api_client import (
    current_page,
    message,
)

@solara.component
def Page():
    TopBar()
    SideMenu()

    with solara.Column(style={"padding": "10px"}):
        if message.value:
            with solara.Card(style={
                "padding": "10px",
                "margin": "10px 0",
                "background": "#fef3c7"
            }):
                solara.Text(message.value)

        if current_page.value == "main":
            MainPage()
        elif current_page.value == "login":
            LoginPage()
        elif current_page.value == "signup":
            SignupPage()
        elif current_page.value == "mypage":
            MyPage()
        else:
            solara.Text("페이지를 찾을 수 없습니다.")