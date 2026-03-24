## 백엔드 FastAPI 호출
## 0320 기준 진짜 API 호출 아직, 상태 관리+임시 데이터 저장소 역할 부여함 -> FastAPI 붙일 때 여기만 바꿈

import solara
import pandas as pd
from pathlib import Path
import random

# =========================
# 전역 상태
# =========================
current_page = solara.reactive("main")     # main / login / signup / mypage
menu_open = solara.reactive(False)

is_logged_in = solara.reactive(False)
current_user = solara.reactive(None)

message = solara.reactive("")

# =========================
# 임시 사용자 저장소
# =========================
users = solara.reactive({
    "admin": {
        "password": "1234",
        "name": "관리자",
        "email": "admin@test.com",
        "role": "분석관"
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
ugv_count = solara.reactive(6)
controller_count = solara.reactive(2)
risk_sensitivity = solara.reactive("중간")
departure = solara.reactive("AOI-START")
destination = solara.reactive("AOI-END")

# 우선순위 카드 예시
warning_cards = solara.reactive([
    {"priority": 1, "title": "주의", "content": "강수 증가로 센서 성능 저하 가능성"},
    {"priority": 2, "title": "주의", "content": "토양수분 상승으로 이동속도 저하 예상"},
    {"priority": 3, "title": "주의", "content": "특정 구간 시야 저하로 재계획 필요"},
])

# 저장용 리포트 예시
report_data = solara.reactive([
    {"time": "10:00", "risk": "Amber", "queue_length": 3, "reroute": True},
    {"time": "10:10", "risk": "Red", "queue_length": 5, "reroute": True},
    {"time": "10:20", "risk": "Amber", "queue_length": 2, "reroute": False},
])

# =========================
# 맵 상태
# =========================
grid_rows = solara.reactive(12)
grid_cols = solara.reactive(16)

# 셀 값 의미:
# 0 = 일반
# 1 = 주의
# 2 = 위험
risk_grid = solara.reactive([[0 for _ in range(grid_cols.value)] for _ in range(grid_rows.value)])

# 경로는 (row, col) 좌표 리스트
planned_path = solara.reactive([])
start_point = solara.reactive((0, 0))
end_point = solara.reactive((grid_rows.value - 1, grid_cols.value - 1))

# 더미 UGV 위치
ugv_positions = solara.reactive([])


# =========================
# 공통 기능
# =========================
def go_page(page_name: str):
    current_page.value = page_name
    menu_open.value = False
    message.value = ""

def toggle_menu():
    menu_open.value = not menu_open.value


# =========================
# 로그인 / 로그아웃 / 회원가입
# =========================
def do_login():
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
    is_logged_in.value = False
    current_user.value = None
    login_id.value = ""
    login_password.value = ""
    message.value = "로그아웃되었습니다."
    current_page.value = "main"

def do_signup():
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

    user_dict[uid] = {
        "password": pw,
        "name": name,
        "email": email,
        "role": "일반 사용자"
    }
    users.value = user_dict

    signup_name.value = ""
    signup_id.value = ""
    signup_password.value = ""
    signup_email.value = ""

    message.value = "회원가입이 완료되었습니다. 로그인해주세요."
    current_page.value = "login"

def update_profile():
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
# 맵 생성 유틸
# =========================
def generate_dummy_risk_grid(rows: int, cols: int):
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            # 기본: 일반
            val = 0

            # 예시용 위험 구역 몇 개 배치
            if 2 <= r <= 4 and 4 <= c <= 6:
                val = 1
            if 6 <= r <= 8 and 8 <= c <= 11:
                val = 2
            if r == 9 and 2 <= c <= 5:
                val = 1
            if c == 13 and 3 <= r <= 9:
                val = 2

            row.append(val)
        grid.append(row)
    return grid

def generate_dummy_path(rows: int, cols: int):
    # 간단한 꺾인 경로 예시
    path = []

    # (0,0)에서 시작해서 아래로 3칸
    for r in range(0, 4):
        path.append((r, 0))

    # 오른쪽으로 6칸
    for c in range(1, 7):
        path.append((3, c))

    # 아래로 4칸
    for r in range(4, 8):
        path.append((r, 6))

    # 오른쪽 끝까지
    for c in range(7, cols):
        path.append((7, c))

    # 마지막 열에서 아래로 끝까지
    for r in range(8, rows):
        path.append((r, cols - 1))

    return path

def generate_dummy_ugv_positions(path, count):
    if not path:
        return []
    step = max(1, len(path) // max(1, count))
    positions = []
    for i in range(count):
        idx = min(i * step, len(path) - 1)
        positions.append(path[idx])
    return positions


# =========================
# 시뮬레이션 예시 동작
# =========================
def run_simulation_mock():
    rows = grid_rows.value
    cols = grid_cols.value

    new_grid = generate_dummy_risk_grid(rows, cols)
    new_path = generate_dummy_path(rows, cols)
    new_ugv_positions = generate_dummy_ugv_positions(new_path, ugv_count.value)

    risk_grid.value = new_grid
    planned_path.value = new_path
    start_point.value = (0, 0)
    end_point.value = (rows - 1, cols - 1)
    ugv_positions.value = new_ugv_positions

    cards = [
        {
            "priority": 1,
            "title": "위험",
            "content": f"UGV {ugv_count.value}대 / 통제관 {controller_count.value}명 기준 대기열 위험 증가"
        },
        {
            "priority": 2,
            "title": "주의",
            "content": f"위험 민감도: {risk_sensitivity.value}, 특정 고위험 셀 우회 필요"
        },
        {
            "priority": 3,
            "title": "권고",
            "content": "붉은 셀 구간은 센서 블랙아웃 및 속도 저하 가능성이 높음"
        },
    ]
    warning_cards.value = cards

    report_data.value = [
        {"time": "10:00", "risk": "Amber", "queue_length": 2, "reroute": False},
        {"time": "10:10", "risk": "Red", "queue_length": 4, "reroute": True},
        {"time": "10:20", "risk": "Red", "queue_length": 5, "reroute": True},
    ]

    message.value = "시뮬레이션 예시 실행 완료: 격자 맵과 경로를 갱신했습니다."