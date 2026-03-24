## 페이지 구성 모아놓은 곳

import solara

from components.grid_view import GridView
from components.cards import WarningCard
from services.api_client import (
    warning_cards,
    login_id,
    login_password,
    signup_name,
    signup_id,
    signup_password,
    signup_email,
    edit_name,
    edit_email,
    is_logged_in,
    current_user,
    users,
    ugv_count,
    controller_count,
    risk_sensitivity,
    departure,
    destination,
    do_login,
    do_signup,
    do_logout,
    update_profile,
    go_page,
    run_simulation_mock,
)

@solara.component
def MainPage():
    with solara.Column(style={"padding": "20px"}):
        solara.Markdown("## 메인 화면")

        with solara.Row(style={"gap": "20px", "align-items": "flex-start"}):
            # 왼쪽: 설정 패널
            with solara.Card(style={
                "width": "20%",
                "min-height": "620px",
                "padding": "12px",
                "background": "#fee2e2"
            }):
                solara.Markdown("### 설정 패널")
                solara.InputInt("UGV 수", value=ugv_count)
                solara.InputInt("통제관 수", value=controller_count)
                solara.InputText("위험 민감도", value=risk_sensitivity)
                solara.InputText("출발지", value=departure)
                solara.InputText("도착지", value=destination)

                solara.Button("시뮬레이션 실행", on_click=run_simulation_mock)

            # 중앙: 전체 격자 맵
            with solara.Card(style={
                "width": "55%",
                "min-height": "620px",
                "padding": "12px"
            }):
                solara.Markdown("### 시뮬레이션 맵")
                solara.Text("전체 맵이 격자 형태로 표시되고, 경로/시작점/도착점/UGV 위치가 함께 출력됩니다.")
                GridView()

            # 오른쪽: 우선순위 카드
            with solara.Card(style={
                "width": "25%",
                "min-height": "620px",
                "padding": "12px",
                "background": "#ecfccb"
            }):
                solara.Markdown("### 우선순위 카드")
                sorted_cards = sorted(warning_cards.value, key=lambda x: x["priority"])
                for card in sorted_cards:
                    WarningCard(
                        priority=card["priority"],
                        title=card["title"],
                        content=card["content"],
                    )

        with solara.Card(style={"margin-top": "20px", "padding": "12px"}):
            solara.Markdown("### 하단 분석 / 로그 영역")
            solara.Text("여기에 KPI, 경로 변경 사유, 이벤트 로그, LTWR 요약 등을 표시")

@solara.component
def LoginPage():
    with solara.Column(style={
        "padding": "20px",
        "max-width": "500px",
        "margin": "0 auto"
    }):
        solara.Markdown("## 로그인")
        solara.InputText("아이디", value=login_id)
        solara.InputText("비밀번호", value=login_password, password=True)

        with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
            solara.Button("로그인", on_click=do_login)
            solara.Button("회원가입으로 이동", on_click=lambda: go_page("signup"))

@solara.component
def SignupPage():
    with solara.Column(style={
        "padding": "20px",
        "max-width": "500px",
        "margin": "0 auto"
    }):
        solara.Markdown("## 회원가입")
        solara.InputText("이름", value=signup_name)
        solara.InputText("아이디", value=signup_id)
        solara.InputText("비밀번호", value=signup_password, password=True)
        solara.InputText("이메일", value=signup_email)

        with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
            solara.Button("회원가입", on_click=do_signup)
            solara.Button("로그인으로 이동", on_click=lambda: go_page("login"))

@solara.component
def MyPage():
    if not is_logged_in.value or not current_user.value:
        with solara.Column(style={"padding": "20px"}):
            solara.Markdown("## 마이페이지")
            solara.Text("로그인이 필요합니다.")
            solara.Button("로그인하기", on_click=lambda: go_page("login"))
        return

    user = users.value[current_user.value]

    with solara.Column(style={
        "padding": "20px",
        "max-width": "700px",
        "margin": "0 auto"
    }):
        solara.Markdown("## 회원 정보 / 마이페이지")

        with solara.Card(style={"padding": "16px"}):
            solara.Text(f"아이디: {current_user.value}")
            solara.Text(f"권한: {user['role']}")
            solara.InputText("이름", value=edit_name)
            solara.InputText("이메일", value=edit_email)

            with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
                solara.Button("정보 수정", on_click=update_profile)
                solara.Button("회원 로그아웃", on_click=do_logout)