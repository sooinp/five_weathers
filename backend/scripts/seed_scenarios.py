"""
scripts/seed_scenarios.py

scenarios 테이블에 기본 시드 데이터를 삽입하는 스크립트.
load_grid.py / load_weather.py 실행 전에 반드시 먼저 실행해야 합니다.

사용법:
    python scripts/seed_scenarios.py              # 기본 시나리오 전체 삽입
    python scripts/seed_scenarios.py --list       # 삽입 예정 시나리오 목록 출력
    python scripts/seed_scenarios.py --dry-run    # DB 반영 없이 삽입 내용 확인

의존성:
    pip install psycopg2-binary python-dotenv
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import execute_values


# ──────────────────────────────────────────────
# 시드 데이터 정의
# ──────────────────────────────────────────────

SCENARIOS = [
    {
        "scenario_id": "scenario_001",
        "name": "하계 주간 기본 작전",
        "description": (
            "맑은 날씨, 주간, 여름 조건의 기본 시나리오. "
            "기상 악조건 없이 UGV 기동성 및 탐지 성능이 최대화되는 표준 환경."
        ),
    },
    {
        "scenario_id": "scenario_002",
        "name": "동계 악천후 작전",
        "description": (
            "강설 및 안개가 동반된 동계 야간 시나리오. "
            "적설로 인한 기동성 저하 및 시계 제한 환경에서의 UGV 운용 평가."
        ),
    },
    {
        "scenario_id": "scenario_003",
        "name": "우기 집중강우 작전",
        "description": (
            "집중호우 상황의 우기 시나리오. "
            "강수로 인한 센서 성능 저하 및 연약지반 기동성 제한 환경."
        ),
    },
    {
        "scenario_id": "scenario_004",
        "name": "도심지 복합지형 작전",
        "description": (
            "시가지와 산림이 혼재된 복합지형 시나리오. "
            "다양한 토지피복(시가지/산림/수계) 조건에서의 경로 최적화 평가."
        ),
    },
    {
        "scenario_id": "scenario_005",
        "name": "실전 모의 종합 평가",
        "description": (
            "실전에 가장 근접한 기상·지형·교전 조건을 종합한 평가 시나리오. "
            "파레토 최적 경로 산출 및 손실 최소화 전략 검증용."
        ),
    },
]


# ──────────────────────────────────────────────
# DB 연결 헬퍼
# ──────────────────────────────────────────────

def get_db_url() -> str:
    script_dir = Path(__file__).resolve().parent
    env_candidates = [
        script_dir.parent / ".env",
        script_dir.parent.parent / ".env",
        Path(".env"),
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
    else:
        load_dotenv()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL 환경 변수가 설정되지 않았습니다.")

    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    return db_url


# ──────────────────────────────────────────────
# 삽입 로직
# ──────────────────────────────────────────────

def seed(conn, scenarios: list[dict], dry_run: bool = False) -> None:
    """
    scenarios 테이블에 시드 데이터 UPSERT.
    이미 존재하는 scenario_id는 name/description만 갱신.
    """
    now = datetime.now(timezone.utc)
    records = [
        (s["scenario_id"], s["name"], s["description"], now)
        for s in scenarios
    ]

    sql = """
        INSERT INTO scenarios (scenario_id, name, description, created_at)
        VALUES %s
        ON CONFLICT (scenario_id)
        DO UPDATE SET
            name        = EXCLUDED.name,
            description = EXCLUDED.description
    """

    if dry_run:
        print("[DRY-RUN] 실제 DB 반영 없이 삽입 내용을 출력합니다.\n")
        for r in records:
            print(f"  scenario_id : {r[0]}")
            print(f"  name        : {r[1]}")
            print(f"  description : {r[2][:60]}...")
            print(f"  created_at  : {r[3].isoformat()}")
            print()
        return

    with conn.cursor() as cur:
        execute_values(cur, sql, records)
    conn.commit()
    print(f"[INFO] {len(records)}개 시나리오 삽입/갱신 완료")
    for r in records:
        print(f"  ✔ {r[0]}  ({r[1]})")


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="scenarios 테이블에 기본 시드 데이터를 삽입합니다."
    )
    parser.add_argument("--list", action="store_true",
                        help="삽입 예정 시나리오 목록만 출력하고 종료")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB에 반영하지 않고 삽입 내용만 확인")
    args = parser.parse_args()

    if args.list:
        print(f"삽입 예정 시나리오 ({len(SCENARIOS)}개):")
        for s in SCENARIOS:
            print(f"  {s['scenario_id']}  {s['name']}")
        return

    if args.dry_run:
        seed(conn=None, scenarios=SCENARIOS, dry_run=True)
        return

    db_url = get_db_url()
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        sys.exit(f"[ERROR] DB 연결 실패: {e}")

    try:
        seed(conn, SCENARIOS)
    finally:
        conn.close()

    print("[INFO] 완료.")


if __name__ == "__main__":
    main()
