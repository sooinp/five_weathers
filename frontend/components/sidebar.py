## 사이드 바 디자인 구성

import solara
from services.api_client import menu_open, is_logged_in, go_page, do_logout, save_report_csv

@solara.component
def SideMenu():
    if not menu_open.value:
        return

    with solara.Card(
        style={
            # overlay 메뉴 구성
            "position": "fixed",
            "top": "56px",
            "left": "10px",
            "width": "220px",
            "z-index": "999",
            "padding": "12px",
            "background": "#eff6ff",
            "border-radius": "18px",
            "box-shadow": "0 10px 24px rgba(15,23,42,0.16)",
        }
    ):
        solara.Button("메인으로 돌아가기", on_click=lambda: go_page("main"), block=True)
        solara.Button("리포트 저장", on_click=save_report_csv, block=True)

        # 로그인 여부에 따라 보여줄 메뉴 분기
        if is_logged_in.value:
            solara.Button("마이페이지", on_click=lambda: go_page("mypage"), block=True)
            solara.Button("로그아웃", on_click=do_logout, block=True)
        else:
            solara.Button("로그인", on_click=lambda: go_page("login"), block=True)
            solara.Button("회원가입", on_click=lambda: go_page("signup"), block=True)
