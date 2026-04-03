## Solara 메인
"""
이 파일은 상단 바, 사이드 메뉴, 본문 페이지를 조립함
페이지 이동 자체는 services/api_client.py의 reactive 상태(current_page)로 제어
"""

import solara
from components.pages import LoginPage, MainPage
from services.api_client import is_logged_in

@solara.component
def Page():
    if not is_logged_in.value:
        LoginPage()
    else:
        MainPage()

app = Page