## 백엔드 FastAPI 호출
## 0327 기준 FastAPI 붙이는 중, 상태 관리+임시 데이터 저장소 역할 부여함
"""
이 파일 하나가 크게 네 역할을 맡는다.
1) Solara reactive 상태 저장소
2) 로그인/회원가입 같은 간단한 프론트 로직
3) FastAPI REST 호출
4) WebSocket 실시간 수신 및 스냅샷 반영
"""

from __future__ import annotations
import asyncio
import os
import threading
from pathlib import Path
import pandas as pd
import requests
import solara
import websockets

# =========================
# 백엔드 연결 설정
# =========================
BACKEND_HTTP_BASE = os.getenv("BACKEND_HTTP_BASE", "http://127.0.0.1:8800")
BACKEND_WS_BASE = os.getenv("BACKEND_WS_BASE", "ws://127.0.0.1:8800")

# =========================
# 전역 상태
# =========================
current_page = solara.reactive("main")     # main / login / signup / mypage
menu_open = solara.reactive(False)

is_logged_in = solara.reactive(False)
current_user = solara.reactive(None)
message = solara.reactive("")
connection_status = solara.reactive("연결 전")
active_run_id = solara.reactive(None)

# WebSocket runtime
# Solara 자체는 async 백그라운드 수신 관리가 번거로워 별도 스레드 + asyncio 루프를 사용
_ws_stop_event = threading.Event()
_ws_thread: threading.Thread | None = None

# =========================
# 임시 사용자 저장소
# =========================
users = solara.reactive({
    "admin": {
        "password": "1234",
        "name": "관리자",
        "email": "admin@test.com",
        "role": "분석관",
    }
})

# 로그인 입력값
login_id = solara.reactive("")
login_password = solara.reactive("")

# 회원가입 입력값
signup_name = solara.reactive("")
signup_id = solara.reactive("")
signup_password = solara.reactive("")
signup_email = solara.reactive("")

# 마이페이지 수정 입력값
edit_name = solara.reactive("")
edit_email = solara.reactive("")

# 시나리오 입력값 예시
# 현재는 좌측 패널에서 보여주는 기본 파라미터 -> 입력 폼과 연결 필요
ugv_count = solara.reactive(6)
controller_count = solara.reactive(2)
risk_sensitivity = solara.reactive("중간")
departure = solara.reactive("AOI-START")
destination = solara.reactive("AOI-END")

# KPI(그리드 맵 하단부)
current_route_label = solara.reactive("현재경로 A-01")
mission_status = solara.reactive("대기")
mission_success_rate = solara.reactive(0)
estimated_cost = solara.reactive(0)
alternative_route = solara.reactive({"name": "차선책 경로 B-02", "success_rate": 0, "cost": 0, "reason": "시뮬레이션 실행 후 표시됩니다."})
mission_time_rows = solara.reactive([])
queue_schedule = solara.reactive([])
selected_unit_id = solara.reactive(None)
selected_detail = solara.reactive(None)

# =========================
# 그리드 맵 상태
# =========================
grid_rows = solara.reactive(12)
grid_cols = solara.reactive(16)

# (risk_grid)셀 값 의미:
# 0 = 일반
# 1 = 주의
# 2 = 위험
terrain_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])
risk_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])
rain_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])
visibility_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])
soil_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])
current_map_tab = solara.reactive("risk")

# 경로는 (row, col) 좌표 리스트
planned_path = solara.reactive([])
start_point = solara.reactive((0, 0))
end_point = solara.reactive((grid_rows.value - 1, grid_cols.value - 1))

# 더미 UGV 위치
ugv_positions = solara.reactive([])
units_data = solara.reactive([])

# 우선순위 카드
# 0327 기준 pages.py에서는 units_data를 직접 써서 카드를 그리지만, warning_cards는 별도 알림 카드 확장용 상태
warning_cards = solara.reactive([])

# 저장용 리포트
report_data = solara.reactive([])

# =========================
# 공통 기능
# =========================
def go_page(page_name: str):
    # 현재 페이지를 변경하고 메뉴/메시지를 정리
    current_page.value = page_name
    menu_open.value = False
    message.value = ""


def toggle_menu():
    # 메뉴 열림/닫힘 상태를 토글
    menu_open.value = not menu_open.value


def select_unit(unit_id: str):
    # 현재 맵에서 강조할 제대 선택
    selected_unit_id.value = unit_id


def open_unit_detail(detail_type: str, unit_id: str):
    # 우측 패널 상세 오버레이
    selected_unit_id.value = unit_id
    selected_detail.value = {"type": detail_type, "unit_id": unit_id}


def close_unit_detail():
    # 상세 오버레이 닫기
    selected_detail.value = None


def get_selected_unit():
    # selected_unit_id에 해당하는 unit dict 반환
    uid = selected_unit_id.value
    for unit in units_data.value:
        if unit["id"] == uid:
            return unit
    return None

# =========================
# 로그인 / 로그아웃 / 회원가입
# =========================
def get_detail_unit():
    # 현재 상세 패널이 가리키는 unit 객체 찾음
    detail = selected_detail.value
    if not detail:
        return None
    for unit in units_data.value:
        if unit["id"] == detail["unit_id"]:
            return unit
    return None


def do_login():
    # 임시 사용자 저장소(users)를 기준으로 로그인 처리 -> 보안 로직 추가 예정
    uid = login_id.value.strip()
    pw = login_password.value.strip()
    user_dict = users.value
    if uid in user_dict and user_dict[uid]["password"] == pw:
        is_logged_in.value = True
        current_user.value = uid
        edit_name.value = user_dict[uid]["name"]
        edit_email.value = user_dict[uid]["email"]
        message.value = f"{user_dict[uid]['name']}님 로그인되었습니다."
        current_page.value = "main"
    else:
        message.value = "아이디 또는 비밀번호가 올바르지 않습니다."


def do_logout():
    # 로그아웃하면서 WebSocket 연결도 함께 정리
    stop_live_updates()
    is_logged_in.value = False
    current_user.value = None
    login_id.value = ""
    login_password.value = ""
    message.value = "로그아웃되었습니다."
    current_page.value = "main"


def do_signup():
    # 임시 사용자 저장소에 새 계정을 추가
    uid = signup_id.value.strip()
    pw = signup_password.value.strip()
    name = signup_name.value.strip()
    email = signup_email.value.strip()
    if not uid or not pw or not name:
        message.value = "이름, 아이디, 비밀번호는 필수입니다."
        return
    user_dict = dict(users.value)
    if uid in user_dict:
        message.value = "이미 존재하는 아이디입니다."
        return
    user_dict[uid] = {"password": pw, "name": name, "email": email, "role": "일반 사용자"}
    users.value = user_dict
    signup_name.value = signup_id.value = signup_password.value = signup_email.value = ""
    message.value = "회원가입이 완료되었습니다. 로그인해주세요."
    current_page.value = "login"


def update_profile():
    # 마이페이지에서 화원정보 수정
    if not current_user.value:
        message.value = "로그인이 필요합니다."
        return
    uid = current_user.value
    user_dict = dict(users.value)
    user_dict[uid]["name"] = edit_name.value.strip()
    user_dict[uid]["email"] = edit_email.value.strip()
    users.value = user_dict
    message.value = "회원 정보가 수정되었습니다."

# =========================
# 리포트 저장
# =========================
def save_report_csv():
    df = pd.DataFrame(report_data.value)
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / "simulation_report.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    message.value = f"리포트가 저장되었습니다: {filename}"

# =========================
# 스냅샷(0327 기준 아직 확실하지 않은 기능 - 삭제될 수도 있어서 그냥 놔둬주세요)
# =========================
def _apply_snapshot(snapshot: dict):
    # snapshot은 백엔드가 화면 전체를 다시 그리기 위해 내려주는 단일 상태 묶음
    grid_rows.value = snapshot.get("rows", grid_rows.value)
    grid_cols.value = snapshot.get("cols", grid_cols.value)
    terrain_grid.value = snapshot.get("terrain_grid", [])
    rain_grid.value = snapshot.get("rain_grid", [])
    visibility_grid.value = snapshot.get("visibility_grid", [])
    soil_grid.value = snapshot.get("soil_grid", [])
    risk_grid.value = snapshot.get("risk_grid", [])
    units_data.value = snapshot.get("units_data", [])
    warning_cards.value = snapshot.get("warning_cards", [])
    planned_path.value = snapshot.get("planned_path", [])
    start_point.value = tuple(snapshot.get("start_point", [0, 0]))
    end_point.value = tuple(snapshot.get("end_point", [0, 0]))
    ugv_positions.value = snapshot.get("ugv_positions", [])
    current_route_label.value = snapshot.get("current_route_label", current_route_label.value)
    mission_status.value = snapshot.get("mission_status", mission_status.value)
    mission_success_rate.value = snapshot.get("mission_success_rate", mission_success_rate.value)
    estimated_cost.value = snapshot.get("estimated_cost", estimated_cost.value)
    alternative_route.value = snapshot.get("alternative_route", alternative_route.value)
    mission_time_rows.value = snapshot.get("mission_time_rows", [])
    queue_schedule.value = snapshot.get("queue_schedule", [])
    report_data.value = snapshot.get("report_data", [])
    if units_data.value and not selected_unit_id.value:
        selected_unit_id.value = units_data.value[0]["id"]


def _http(method: str, path: str, **kwargs):
    # 공통 requests 래퍼. base URL과 timeout을 한곳에서 통일
    return requests.request(method, f"{BACKEND_HTTP_BASE}{path}", timeout=5, **kwargs)

# =========================
# 백엔드와 연결(REST)
# =========================
def check_backend_health():
    # 백엔드 health endpoint를 호출해 REST 연결 가능 여부를 확인
    try:
        response = _http("GET", "/api/v1/simulations/health")
        response.raise_for_status()
        connection_status.value = "REST 연결됨"
        return True
    except Exception as exc:
        connection_status.value = "백엔드 연결 실패"
        message.value = f"백엔드 연결에 실패했습니다: {exc}"
        return False

# =========================
# 시뮬레이션 동작부
# =========================
def start_live_simulation():
    # REST로 시뮬레이션을 시작하고, 성공하면 WebSocket 수신 스레드
    stop_live_updates()
    if not check_backend_health():
        return
    payload = {
        "rows": grid_rows.value,
        "cols": grid_cols.value,
        "ugv_count": ugv_count.value,
        "controller_count": controller_count.value,
        "risk_sensitivity": risk_sensitivity.value,
        "departure": departure.value,
        "destination": destination.value,
        "step_interval_sec": 1.0,
    }
    try:
        response = _http("POST", "/api/v1/simulations/start", json=payload)
        response.raise_for_status()
        data = response.json()["data"]
        active_run_id.value = data["run_id"]
        _apply_snapshot(data["snapshot"])
        message.value = f"REST로 시뮬레이션을 시작했습니다. run_id={active_run_id.value}"
        _start_ws_thread(active_run_id.value)
    except Exception as exc:
        message.value = f"시뮬레이션 시작 실패: {exc}"


def send_simulation_command(action: str):
    # pause/resume/tick 명령을 전송하고 반환된 snapshot으로 즉시 갱신
    if not active_run_id.value:
        message.value = "먼저 시뮬레이션을 실행하세요."
        return
    try:
        response = _http("POST", f"/api/v1/simulations/{active_run_id.value}/command", json={"action": action})
        response.raise_for_status()
        snapshot = response.json()["data"]["snapshot"]
        _apply_snapshot(snapshot)
        message.value = f"명령 전송 완료: {action}"
    except Exception as exc:
        message.value = f"명령 전송 실패: {exc}"


def fetch_latest_snapshot():
    # 현재 run_id의 최신 snapshot을 수동 조회
    if not active_run_id.value:
        return
    try:
        response = _http("GET", f"/api/v1/simulations/{active_run_id.value}/snapshot")
        response.raise_for_status()
        snapshot = response.json()["data"]["snapshot"]
        _apply_snapshot(snapshot)
    except Exception as exc:
        message.value = f"스냅샷 조회 실패: {exc}"


def stop_live_updates():
    # WebSocket 수신 스레드를 종료하고 연결 상태를 초기화
    global _ws_thread
    _ws_stop_event.set()
    if _ws_thread and _ws_thread.is_alive():
        _ws_thread.join(timeout=1.5)
    _ws_thread = None
    _ws_stop_event.clear()
    connection_status.value = "연결 종료"

# =========================
# 통신(웹소켓 연결) 정의
# =========================
async def _ws_listener(run_id: str):
    # WebSocket 연결 +  이벤트 수신.. 끊기면 자동 재연결 시도
    ws_url = f"{BACKEND_WS_BASE}/api/v1/simulations/ws/{run_id}"
    while not _ws_stop_event.is_set():
        try:
            connection_status.value = "WebSocket 연결 중"
            async with websockets.connect(ws_url, ping_interval=10, ping_timeout=10) as websocket:
                connection_status.value = "WebSocket 연결됨"
                # 서버가 보내는 모든 이벤트는 JSON 문자열
                async for raw in websocket:
                    if _ws_stop_event.is_set():
                        break
                    import json
                    event = json.loads(raw) if isinstance(raw, str) else raw
                    _handle_ws_event(event)
        except Exception as exc:
            connection_status.value = "WebSocket 재연결 중"
            message.value = f"WebSocket 연결 재시도: {exc}"
            await asyncio.sleep(1.5)


def _run_ws_loop(run_id: str):
    # 별도 스레드에서 asyncio 이벤트 루프를 실행하기 위한 래퍼
    asyncio.run(_ws_listener(run_id))


def _start_ws_thread(run_id: str):
    # 현재 run_id 전용 WebSocket 백그라운드 스레드 시작
    global _ws_thread
    _ws_stop_event.clear()
    _ws_thread = threading.Thread(target=_run_ws_loop, args=(run_id,), daemon=True)
    _ws_thread.start()


def _handle_ws_event(event: dict):
    # WebSocket 이벤트 타입에 따라 snapshot 반영 또는 경보 메시지 갱신
    event_type = event.get("event")
    if event_type in {"simulation_snapshot", "simulation_tick", "simulation_state_changed"}:
        snapshot = event.get("snapshot", {})
        _apply_snapshot(snapshot)
        connection_status.value = f"WebSocket 수신 중 · step {snapshot.get('current_step', 0)}"
    elif event_type == "alert_created":
        alert = event.get("alert", {})
        message.value = f"[{alert.get('level','INFO')}] {alert.get('message','새 경보') }"

