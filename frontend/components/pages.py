## 페이지 구성 모아놓은 곳
## 0327 기준 MainPage가 핵심, Login/Signup/MyPage는 부가페이지임

import solara
from components.cards import DetailOverlay, UnitPriorityCard
from components.grid_view import GridView
from services.api_client import (
    alternative_route,
    controller_count,
    current_user,
    departure,
    destination,
    do_login,
    do_logout,
    do_signup,
    edit_email,
    edit_name,
    get_detail_unit,
    is_logged_in,
    login_id,
    login_password,
    message,
    mission_time_rows,
    open_unit_detail,
    queue_schedule,
    risk_sensitivity,
    check_backend_health,
    fetch_latest_snapshot,
    send_simulation_command,
    start_live_simulation,
    stop_live_updates,
    select_unit,
    selected_detail,
    selected_unit_id,
    signup_email,
    signup_id,
    signup_name,
    signup_password,
    ugv_count,
    units_data,
    update_profile,
    users,
)

@solara.component
def _UnitIdentityPanel(unit: dict, is_selected: bool):
    # 좌측 패널의 제대 기본 정보 카드
    # 기본 속성/변수 보여주는 곳
    # 카드 클릭 시 맵에서 경로 강조
    border = f"2px solid {unit['color']}" if is_selected else "1px solid #d1d5db"
    shadow = "0 10px 22px rgba(15,23,42,0.12)" if is_selected else "0 4px 12px rgba(15,23,42,0.06)"

    with solara.Card(
        style={
            "margin-bottom": "10px",
            "padding": "12px",
            "border": border,
            "border-radius": "16px",
            "background": "white",
            "position": "relative",
            "box-shadow": shadow,
            "cursor": "pointer",
        }
    ):
        # 카드 전체 클릭용 투명 버튼
        solara.Button(
            "",
            on_click=lambda: select_unit(unit["id"]),
            style={
                "position": "absolute",
                "inset": "0",
                "width": "100%",
                "height": "100%",
                "opacity": "0.01",
                "z-index": "5",
                "min-width": "100%",
            },
        )
        solara.Markdown(f"**{unit['name']} ({unit['identity']})**")
        solara.Text(f"출발지: {unit['start']}")
        solara.Text(f"도착지: {unit['end']}")
        solara.Text(f"LTWR: {unit['ltwr']} / SOS: {'O' if unit['sos'] else 'X'}")
        solara.Text(f"아이덴티티 컬러: {unit['color']}")


@solara.component
def _RightPanel():
    # 우측 패널: 제대 목록 + LTWR/SOS 상세 오버레이
    detail = selected_detail.value
    detail_unit = get_detail_unit()

    with solara.Card(
        style={
            "width": "26%",
            "min-height": "700px",
            "padding": "14px",
            "background": "#f3f8e8",
            "border-radius": "22px",
            "position": "relative",
        }
    ):
        solara.Markdown("### 우선순위 / 제대 상태")
        solara.Text("스크롤로 제대 카드를 탐색하고 LTWR 또는 SOS를 눌러 상세 정보를 확인합니다.")

        with solara.Column(
            style={
                # 카드가 많아져도 우측 패널 전체 높이는 유지하고 내부만 스크롤
                "height": "620px",
                "overflow-y": "auto",
                "padding-right": "4px",
                "margin-top": "8px",
            }
        ):
            for unit in units_data.value:
                UnitPriorityCard(unit=unit, is_selected=selected_unit_id.value == unit["id"])

        if detail and detail_unit:
            DetailOverlay(detail=detail, unit=detail_unit)


@solara.component
def MainPage():
    # 메인 대시보드
    # 좌측: 시뮬레이션 제어 및 제대 기본 정보
    # 중앙: 전술 맵 + KPI 카드
    # 우측: 우선순위 / 상세 패널

    units = units_data.value

    with solara.Column(style={"padding": "12px 16px 18px 16px", "gap": "14px"}):
        with solara.Row(style={"gap": "16px", "align-items": "flex-start"}):
            # 왼쪽: 시뮬레이션 입력/제어 영역 + 제대 기본 정보
            with solara.Card(
                style={
                    "width": "20%",
                    "min-height": "700px",
                    "padding": "14px",
                    "background": "#fff7ed",
                    "border-radius": "22px",
                }
            ):
                solara.Markdown("### 제대 기본 정보")
                solara.Text(f"현재 경로 기준 UGV 수: {ugv_count.value}")
                solara.Text(f"통제관 수: {controller_count.value}")
                solara.Text(f"위험 민감도: {risk_sensitivity.value}")
                solara.Text(f"공통 출발지: {departure.value}")
                solara.Text(f"공통 도착지: {destination.value}")

                # REST / WebSocket 시뮬레이션 흐름을 직접 시험해 볼 수 있게 버튼을 분리함
                solara.Button("백엔드 상태 확인", on_click=check_backend_health)
                solara.Button("시뮬레이션 실행", on_click=start_live_simulation)
                solara.Button("일시정지", on_click=lambda: send_simulation_command("pause"))
                solara.Button("재개", on_click=lambda: send_simulation_command("resume"))
                solara.Button("1틱 진행", on_click=lambda: send_simulation_command("tick"))
                solara.Button("스냅샷 조회", on_click=fetch_latest_snapshot)
                solara.Button("연결 종료", on_click=stop_live_updates)
                solara.Button("선택 해제", on_click=lambda: setattr(selected_unit_id, "value", None))

                with solara.Column(style={"margin-top": "10px"}):
                    for unit in units:
                        _UnitIdentityPanel(unit=unit, is_selected=selected_unit_id.value == unit["id"])

            # 중앙: 전술 맵과 하단 KPI 카드(맵 하단) 묶음
            with solara.Column(style={"width": "54%", "gap": "12px"}):
                with solara.Card(
                    style={
                        "min-height": "520px",
                        "padding": "14px",
                        "border-radius": "22px",
                        "background": "white",
                    }
                ):
                    solara.Markdown("### 시뮬레이션 맵")
                    solara.Text("지형은 공통으로 유지되고, 강수 · 시정 · 토양수분 · 미션 위험도 레이어를 탭으로 전환해 확인할 수 있습니다.")
                    GridView()

                with solara.Row(style={"gap": "12px", "align-items": "stretch"}):
                    with solara.Card(style={"width": "36%", "padding": "14px", "border-radius": "18px"}):
                        solara.Markdown("### 차선책 경로")
                        solara.Text(alternative_route.value["name"])
                        solara.Text(f"임무 성공률: {alternative_route.value['success_rate']}%")
                        solara.Text(f"예상 비용: {alternative_route.value['cost']} ₩")
                        solara.Text(alternative_route.value["reason"])

                    with solara.Card(style={"width": "32%", "padding": "14px", "border-radius": "18px"}):
                        solara.Markdown("### 남은 시간")
                        # mission_time_rows는 백엔드 스냅샷에서 내려오는 요약 테이블(0327 기준 불확실한 기능)
                        for row in mission_time_rows.value:
                            solara.Text(f"{row['unit']} | {row['ugv']} | {row['manned']} | {row['remaining']}")

                    with solara.Card(style={"width": "32%", "padding": "14px", "border-radius": "18px"}):
                        solara.Markdown("### 대기열")
                        for item in queue_schedule.value:
                            solara.Text(f"• {item['unit']} {item['asset']} / {item['wait']}")
                            solara.Text(f"  - {item['priority']}")

            # 오른쪽: 우선순위 스크롤 카드 + 상세 탭
            _RightPanel()


@solara.component
def LoginPage():
    # 로그인 페이지. 0327 현재 데모용 임시 사용자 저장소(users) 사용중, 로직 추가 예정
    with solara.Column(style={"padding": "20px", "max-width": "500px", "margin": "0 auto"}):
        solara.Markdown("## 로그인")
        solara.InputText("아이디", value=login_id)
        solara.InputText("비밀번호", value=login_password, password=True)
        with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
            solara.Button("로그인", on_click=do_login)


@solara.component
def SignupPage():
    # 회원가입 페이지. 0327 기준 보안 관련 로직 추가 예정
    with solara.Column(style={"padding": "20px", "max-width": "500px", "margin": "0 auto"}):
        solara.Markdown("## 회원가입")
        solara.InputText("이름", value=signup_name)
        solara.InputText("아이디", value=signup_id)
        solara.InputText("비밀번호", value=signup_password, password=True)
        solara.InputText("이메일", value=signup_email)
        with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
            solara.Button("회원가입", on_click=do_signup)


@solara.component
def MyPage():
    # 마이페이지. 회원가입 내용을 기준으로 작성된 내용을 수정할 수 있음
    # -> 0327 기준 제대 변경, 소속 변경 등 추가 적용 예정
    if not is_logged_in.value or not current_user.value:
        with solara.Column(style={"padding": "20px"}):
            solara.Markdown("## 마이페이지")
            solara.Text("로그인이 필요합니다.")
        return

    user = users.value[current_user.value]
    with solara.Column(style={"padding": "20px", "max-width": "700px", "margin": "0 auto"}):
        solara.Markdown("## 회원 정보 / 마이페이지")
        with solara.Card(style={"padding": "16px"}):
            solara.Text(f"아이디: {current_user.value}")
            solara.Text(f"권한: {user['role']}")
            solara.InputText("이름", value=edit_name)
            solara.InputText("이메일", value=edit_email)
            with solara.Row(style={"gap": "10px", "margin-top": "10px"}):
                solara.Button("정보 수정", on_click=update_profile)
                solara.Button("회원 로그아웃", on_click=do_logout)
