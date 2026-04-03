## 페이지 구성 모아놓은 곳
## 0327 기준 MainPage가 핵심, Login/Signup/MyPage는 부가페이지임

import solara
from components.grid_view import GridView
from components.cards import LtwrMapPanel
from services.api_client import (
    input_username,
    input_password,
    login_error,
    attempt_login,
    logged_in_user,
    NICKNAMES,
    go_home,
    active_btn,
    set_active_button,
    success_rate,
    asset_damage,
    status,
    time_left,
    ratio_x,
    effect_success,
    effect_damage,
    queue_data,
)

@solara.component
def LoginPage():
    solara.Style("""
        .login-bg {
            background-color: #0b1426 !important;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .login-card {
            padding: 40px;
            background-color: rgba(22, 34, 56, 0.9) !important;
            border: 1px solid #2d3a54 !important;
            border-radius: 16px;
            width: 400px;
            color: white !important;
        }
        input { color: white !important; }
        .v-label { color: #94a3b8 !important; }
    """)

    with solara.Div(classes=["login-bg"]):
        with solara.Div(classes=["login-card"]):
            solara.Text(
                "Mission Control System",
                style={
                    "font-size": "26px",
                    "font-weight": "bold",
                    "text-align": "center",
                    "margin-bottom": "30px",
                    "display": "block",
                },
            )
            solara.InputText(
                "사용자 아이디",
                value=input_username.value,
                on_value=input_username.set,
            )
            solara.InputText(
                "비밀번호",
                value=input_password.value,
                on_value=input_password.set,
                password=True,
            )

            if login_error.value:
                solara.Text(
                    "정보가 올바르지 않습니다.",
                    style={
                        "color": "#fb7185",
                        "font-size": "14px",
                        "margin-top": "10px",
                        "display": "block",
                        "text-align": "center",
                    },
                )

            solara.Button(
                "Login to Dashboard",
                on_click=attempt_login,
                style={
                    "background-color": "#2d3a54",
                    "color": "white",
                    "height": "50px",
                    "width": "100%",
                    "margin-top": "20px",
                },
            )

@solara.component
def MainPage():
    unit_name = NICKNAMES.get(logged_in_user.value, "미확인")

    solara.Style("""
        html, body, #app, .v-application, .v-application--wrap,
        .solara-content-main, .solara-app, .v-main {
            background-color: #0b1426 !important;
            color: white !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }

        .page-root {
            width: 100vw;
            height: 100vh;
            background: #0b1426;
            overflow: hidden;
            box-sizing: border-box;
            padding: 20px;
        }

        .page-shell {
            width: 100%;
            height: 100%;
            display: grid;
            grid-template-columns: 280px minmax(0, 1fr) 390px;
            grid-template-rows: 104px minmax(0, 1fr);
            gap: 14px;
            box-sizing: border-box;
        }

        .top-sidebar-bar {
            grid-column: 1 / 3;
            grid-row: 1;
            width: 100%;
            height: 104px;
            display: grid;
            grid-template-columns: 120px 1.8fr 0.9fr 0.9fr 0.9fr 0.9fr;
            gap: 10px;
            background-color: rgba(22, 34, 56, 0.7) !important;
            border-radius: 12px;
            padding: 10px;
            box-sizing: border-box;
        }

        .content-grid-left {
            grid-column: 1 / 3;
            grid-row: 2;
            width: 100%;
            min-height: 0;
            display: grid;
            grid-template-columns: 280px minmax(0, 1fr);
            gap: 14px;
            box-sizing: border-box;
        }

        .status-item-box {
            background-color: rgba(15, 23, 38, 0.7) !important;
            border: 1px solid rgba(45, 58, 84, 0.5) !important;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            padding: 0 12px !important;
            min-width: 0;
            box-sizing: border-box;
            overflow: hidden;
        }

        .item-title {
            color: #94a3b8 !important;
            font-size: 13px !important;
            margin-bottom: 4px;
            font-weight: bold;
            white-space: nowrap;
        }

        .item-value {
            font-size: 26px !important;
            font-weight: 600;
            color: white !important;
            white-space: nowrap;
        }

        .action-btn {
            height: 38px !important;
            width: 82px !important;
            font-size: 14px !important;
            font-weight: bold !important;
            border-radius: 6px !important;
            padding: 0 !important;
            transition: all 0.2s ease;
        }

        .btn-active {
            background-color: #e67e22 !important;
            color: white !important;
            opacity: 1 !important;
        }

        .btn-default {
            background-color: #2d3a54 !important;
            color: white !important;
            opacity: 0.8 !important;
        }

        .left-sub-sidebar {
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        .sub-inner-card {
            background-color: rgba(15, 23, 38, 0.8) !important;
            border: 1px solid rgba(45, 58, 84, 0.5) !important;
            border-radius: 12px;
            padding: 15px;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }

        .center-map-area {
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
            background-color: rgba(15, 23, 38, 0.8) !important;
            border: 1px solid rgba(45, 58, 84, 0.5) !important;
            border-radius: 12px;
            padding: 14px;
            box-sizing: border-box;
            overflow: hidden;
        }

        .right-sidebar-area {
            grid-column: 3;
            grid-row: 1 / 3;
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
            background-color: rgba(22, 34, 56, 0.5) !important;
            border: 1px solid rgba(45, 58, 84, 0.5) !important;
            border-radius: 12px;
            padding: 14px;
            box-sizing: border-box;
            overflow-y: auto;
        }

        .right-sidebar-area::-webkit-scrollbar { width: 8px; }
        .right-sidebar-area::-webkit-scrollbar-track { background: rgba(11, 20, 38, 0.5); }
        .right-sidebar-area::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
        .right-sidebar-area::-webkit-scrollbar-thumb:hover { background: #2d3a54; }

        div { background-color: transparent !important; }

        .card-label {
            color: #94a3b8 !important;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
        }
                 
        .queue-danger-item {
            background-color: #6a3844 !important;
        }

        .effect-label {
            color: #cbd5e1 !important;
        }
    """)

    with solara.Div(classes=["page-root"]):
        with solara.Div(classes=["page-shell"]):
            with solara.Div(classes=["top-sidebar-bar"]):
                with solara.Div(classes=["status-item-box"], style={"align-items": "center"}):
                    solara.Button(
                        "⬅︎",
                        on_click=go_home,
                        style={
                            "background-color": "#1e293b",
                            "color": "white",
                            "width": "70%",
                            "font-size": "24px",
                        },
                    )

                with solara.Div(classes=["status-item-box"]):
                    solara.Text("현재 경로", classes=["item-title"])
                    with solara.Row(gap="5px", justify="start"):
                        for b in ["실행", "일시정지", "종료"]:
                            solara.Button(
                                b,
                                on_click=lambda x=b: set_active_button(x),
                                classes=[
                                    "action-btn",
                                    "btn-active" if active_btn.value == b else "btn-default",
                                ],
                            )

                items = [
                    ("진행 상황", status.value),
                    ("임무성공률", f"{success_rate.value}%"),
                    ("자산피해율", f"{asset_damage.value}%"),
                    ("남은시간", time_left.value),
                ]

                for label, val in items:
                    with solara.Div(classes=["status-item-box"]):
                        solara.Text(label, classes=["item-title"])
                        solara.Text(val, classes=["item-value"])

            with solara.Div(classes=["content-grid-left"]):
                with solara.Div(classes=["left-sub-sidebar"]):
                    with solara.Div(classes=["sub-inner-card"], style={"padding": "0"}):
                        with solara.Row(style={"flex": "1", "gap": "0px", "padding": "15px"}):
                            with solara.Column(style={"flex": "1", "padding": "0"}):
                                solara.Text("부대 정보", classes=["card-label"], style={"margin-left": "5px"})
                                solara.Text(
                                    unit_name,
                                    style={
                                        "font-size": "24px",
                                        "font-weight": "bold",
                                        "text-align": "center",
                                        "color": "white",
                                    },
                                )

                            with solara.Column(
                                style={
                                    "flex": "1",
                                    "padding": "0",
                                    "border-left": "1px solid rgba(45,58,84,0.3)",
                                }
                            ):
                                solara.Text("편성 비율", classes=["card-label"], style={"margin-left": "15px"})
                                solara.Text(
                                    f"{ratio_x.value} : 1",
                                    style={
                                        "font-size": "24px",
                                        "font-weight": "bold",
                                        "text-align": "center",
                                        "color": "white",
                                    },
                                )

                    with solara.Div(classes=["sub-inner-card"]):
                        solara.Text("현재경로 효과", classes=["card-label"])

                        with solara.Div(
                            style={
                                "display": "flex",
                                "justify-content": "space-between",
                                "margin-bottom": "4px",
                            }
                        ):
                            solara.Text("임무성공률", classes=["effect-label"])
                            solara.Text(
                                f"+{effect_success.value}%",
                                style={"color": "#4ade80", "font-weight": "bold"},
                            )

                        with solara.Div(
                            style={
                                "display": "flex",
                                "justify-content": "space-between",
                            }
                        ):
                            solara.Text("자산피해율", classes=["effect-label"])
                            solara.Text(
                                f"{effect_damage.value}%",
                                style={"color": "#fb7185", "font-weight": "bold"},
                            )

                    with solara.Div(
                        classes=["sub-inner-card"],
                        style={"flex": "1", "min-height": "0"},
                    ):
                        solara.Text("대기열", classes=["card-label"])
                        solara.Text(
                            "UGV's in danger",
                            style={
                                "font-size": "12px",
                                "color": "#64748b",
                                "margin-top": "-8px",
                            },
                        )

                        for item in queue_data.value[:4]:
                            with solara.Div(
                                classes=["queue-danger-item"],
                                style={
                                    "border-radius": "8px",
                                    "padding": "10px 12px",
                                    "margin-top": "10px",
                                    "display": "flex",
                                    "justify-content": "space-between",
                                    "align-items": "center",
                                }
                            ):
                                solara.Text(
                                    item["id"],
                                    style={
                                        "font-weight": "bold",
                                        "color": "white",
                                        "font-size": "14px",
                                    },
                                )
                                solara.Text(
                                    item["dist"],
                                    style={
                                        "color": "white",
                                        "font-size": "14px",
                                        "font-weight": "600",
                                    },
                                )

                GridView()
            LtwrMapPanel()