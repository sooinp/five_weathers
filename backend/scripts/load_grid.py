"""
scripts/load_grid.py

sim_input_200m_bbox_50km.parquet → grid_cells 테이블 bulk insert 스크립트

사용법:
    python scripts/load_grid.py \
        --scenario-id scenario_001 \
        --parquet-file server/sample/정적\ 지형\ 및\ 도로\ 재처리\ 파일/sim_input_200m_bbox_50km.parquet

의존성:
    pip install pandas pyarrow psycopg2-binary python-dotenv
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# CGLS 토지피복 코드 → 문자열 매핑
LC_CODE_MAP = {
    10: "농경지",
    30: "초지",
    40: "관목지",
    50: "시가지",
    60: "산림",
    80: "수계",
    90: "습지",
}


def get_db_url() -> str:
    """
    .env 파일에서 DATABASE_URL을 읽어 psycopg2용 DSN으로 변환.
    asyncpg URL (postgresql+asyncpg://...) → psycopg2 URL (postgresql://...).
    """
    # 스크립트 위치에서 backend 루트의 .env 탐색
    script_dir = Path(__file__).resolve().parent
    env_candidates = [
        script_dir.parent / ".env",          # server/backend/.env
        script_dir.parent.parent / ".env",   # server/.env
        Path(".env"),                         # 현재 디렉터리
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
    else:
        load_dotenv()  # 환경 변수에서 직접 읽기 시도

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL 환경 변수가 설정되지 않았습니다.")

    # asyncpg 드라이버 접두사 제거
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    return db_url


def load_parquet(parquet_file: str) -> pd.DataFrame:
    """parquet 파일을 읽어 필요한 컬럼만 반환."""
    path = Path(parquet_file)
    if not path.exists():
        sys.exit(f"[ERROR] parquet 파일을 찾을 수 없습니다: {path}")

    print(f"[INFO] parquet 로드 중: {path}")
    df = pd.read_parquet(path, columns=[
        "cell_id", "lat", "lon", "lc_code", "mask_good", "roads_has_drivable_road"
    ])
    print(f"[INFO] 로드 완료: {len(df):,}행")
    return df


def transform(df: pd.DataFrame, scenario_id: str) -> list[tuple]:
    """
    DataFrame → grid_cells INSERT용 튜플 리스트 변환.

    반환 컬럼 순서:
        grid_id, scenario_id, lat, lon, land_cover_type, is_safe_area, road_type
    """
    df = df.copy()

    # lc_code → land_cover_type 문자열 변환 (미등록 코드는 "unknown"으로 처리)
    df["land_cover_type"] = df["lc_code"].map(LC_CODE_MAP).fillna("unknown")

    # roads_has_drivable_road → road_type
    df["road_type"] = df["roads_has_drivable_road"].apply(
        lambda x: "paved" if bool(x) else "none"
    )

    # is_safe_area: bool 보장
    df["is_safe_area"] = df["mask_good"].astype(bool)

    records = [
        (
            str(row.cell_id),
            scenario_id,
            float(row.lat),
            float(row.lon),
            row.land_cover_type,
            row.is_safe_area,
            row.road_type,
        )
        for row in df.itertuples(index=False)
    ]
    return records


def insert_grid_cells(conn, records: list[tuple], batch_size: int = 5000) -> None:
    """
    psycopg2 execute_values로 grid_cells 테이블에 bulk insert.
    기존 데이터 충돌 시 무시 (ON CONFLICT DO NOTHING).
    """
    sql = """
        INSERT INTO grid_cells
            (grid_id, scenario_id, lat, lon, land_cover_type, is_safe_area, road_type)
        VALUES %s
        ON CONFLICT (grid_id) DO NOTHING
    """
    total = len(records)
    inserted = 0

    with conn.cursor() as cur:
        for start in range(0, total, batch_size):
            batch = records[start : start + batch_size]
            execute_values(cur, sql, batch, page_size=batch_size)
            inserted += len(batch)
            print(f"[INFO] 진행: {inserted:,}/{total:,}행 삽입 완료", end="\r")

    conn.commit()
    print(f"\n[INFO] 전체 {total:,}행 삽입 완료")


def main():
    parser = argparse.ArgumentParser(
        description="parquet 파일을 grid_cells 테이블에 적재합니다."
    )
    parser.add_argument(
        "--scenario-id",
        required=True,
        help="scenarios 테이블에 존재하는 scenario_id (예: scenario_001)",
    )
    parser.add_argument(
        "--parquet-file",
        required=True,
        help="입력 parquet 파일 경로",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="한 번에 삽입할 행 수 (기본값: 5000)",
    )
    args = parser.parse_args()

    db_url = get_db_url()

    # 데이터 로드 및 변환
    df = load_parquet(args.parquet_file)
    records = transform(df, args.scenario_id)

    # DB 연결 및 삽입
    print(f"[INFO] DB 연결 중...")
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        sys.exit(f"[ERROR] DB 연결 실패: {e}")

    try:
        # scenario_id 존재 확인
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scenario_id FROM scenarios WHERE scenario_id = %s",
                (args.scenario_id,),
            )
            if cur.fetchone() is None:
                sys.exit(
                    f"[ERROR] scenario_id '{args.scenario_id}'가 scenarios 테이블에 없습니다. "
                    "먼저 시나리오를 생성하세요."
                )

        print(f"[INFO] scenario_id='{args.scenario_id}' 확인 완료")
        insert_grid_cells(conn, records, batch_size=args.batch_size)

    finally:
        conn.close()

    print("[INFO] 완료.")


if __name__ == "__main__":
    main()
