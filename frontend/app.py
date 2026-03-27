## Solara 메인
"""
이 파일은 상단 바, 사이드 메뉴, 본문 페이지를 조립함
페이지 이동 자체는 services/api_client.py의 reactive 상태(current_page)로 제어
"""

import solara
from components.topbar import TopBar
from components.sidebar import SideMenu
from components.pages import MainPage, LoginPage, SignupPage, MyPage
from services.api_client import (
    current_page,
    message,
    connection_status,
)

@solara.component
def Page():
    # 공통 레이아웃: 모든 페이지에서 상단 바와 사이드 메뉴를 먼저 렌더링
    TopBar()
    SideMenu()

    with solara.Column(style={"padding": "10px"}):
        # 전역 메시지 영역: 로그인 결과, 백엔드 연결 상태, WebSocket 재연결 안내 등을 보여줌
        if message.value:
            with solara.Card(style={
                "padding": "10px",
                "margin": "10px 0",
                "background": "#fef3c7"
            }):
                solara.Text(message.value)
                solara.Text(f"통신 상태: {connection_status.value}")

        # current_page 값에 따라 본문을 교체하는 라우팅 구조
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