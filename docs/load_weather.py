"""
scripts/load_weather.py

ERA5-Land NetCDF → weather_forecasts 테이블 bulk insert 스크립트

사용법:
    python scripts/load_weather.py \
        --scenario-id scenario_001 \
        --nc-file server/sample/land/ERA5_land_2022_06.nc \
        --parquet-file "server/sample/정적 지형 및 도로 재처리 파일/sim_input_200m_bbox_50km.parquet"

동작 흐름:
    1. NetCDF에서 시간별 기상 변수(강수량, 적설, 안개확률) 추출
    2. parquet의 grid_cells 위/경도로 ERA5 최근접 격자점 매핑 (KD-Tree)
    3. 기동비용(mobility_cost), 탐지비용(sensor_cost), 종합비용(total_cost) 산출
    4. weather_forecasts 테이블에 bulk insert

ERA5-Land 변수 매핑:
    tp   (total precipitation, m/hr)  → rain_rate (mm/hr)
    sd   (snow depth water equiv., m) → snow_depth (m)
    d2m, t2m (이슬점/기온, K)          → fog_prob (0~1, 상대습도 기반 추정)

비용 산출 공식 (휴리스틱):
    mobility_cost = rain_rate * 0.3 + snow_depth * 10.0 + fog_prob * 0.2  (0~1 클램핑)
    sensor_cost   = fog_prob * 0.6 + rain_rate * 0.1 + snow_depth * 0.05  (0~1 클램핑)
    total_cost    = mobility_cost * 0.6 + sensor_cost * 0.4

의존성:
    pip install xarray netCDF4 scipy pandas pyarrow psycopg2-binary python-dotenv numpy
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import xarray as xr
from scipy.spatial import cKDTree


# ──────────────────────────────────────────────
# DB 연결 헬퍼 (load_grid.py와 동일 로직)
# ──────────────────────────────────────────────

def get_db_url() -> str:
    """
    .env에서 DATABASE_URL을 읽어 psycopg2용 DSN으로 변환.
    asyncpg URL (postgresql+asyncpg://...) → psycopg2 URL (postgresql://).
    """
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
# NetCDF 로드 및 변수 추출
# ──────────────────────────────────────────────

# ERA5-Land에서 사용할 변수명 후보 (버전마다 다를 수 있음)
_VAR_ALIASES = {
    "tp":  ["tp", "total_precipitation"],
    "sd":  ["sd", "snow_depth"],
    "t2m": ["t2m", "2m_temperature"],
    "d2m": ["d2m", "2m_dewpoint_temperature"],
}


def _find_var(ds: xr.Dataset, key: str) -> str | None:
    """데이터셋에서 변수 후보 중 존재하는 첫 번째 이름 반환."""
    for alias in _VAR_ALIASES[key]:
        if alias in ds:
            return alias
    return None


def load_netcdf(nc_file: str) -> xr.Dataset:
    path = Path(nc_file)
    if not path.exists():
        sys.exit(f"[ERROR] NetCDF 파일을 찾을 수 없습니다: {path}")
    print(f"[INFO] NetCDF 로드 중: {path}")
    ds = xr.open_dataset(path)
    print(f"[INFO] 변수: {list(ds.data_vars)}")
    print(f"[INFO] 시간 스텝 수: {ds.dims.get('time', 'N/A')}")
    return ds


def extract_era5_coords(ds: xr.Dataset) -> tuple[np.ndarray, np.ndarray]:
    """
    ERA5 격자의 위/경도 1-D 배열 반환.
    좌표 이름이 latitude/longitude 또는 lat/lon 둘 다 처리.
    """
    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    return ds[lat_name].values, ds[lon_name].values


def compute_fog_prob(t2m_k: np.ndarray, d2m_k: np.ndarray) -> np.ndarray:
    """
    이슬점 온도와 기온의 차이로 상대습도 근사 → 안개 확률 추정.
    RH ≈ 100 - 5 * (T - Td)  (Magnus 근사)
    fog_prob = clamp((RH - 85) / 15, 0, 1)  → RH 85% 이상부터 안개 발생 가능
    """
    t_c = t2m_k - 273.15
    d_c = d2m_k - 273.15
    rh = 100.0 - 5.0 * (t_c - d_c)
    rh = np.clip(rh, 0.0, 100.0)
    fog = np.clip((rh - 85.0) / 15.0, 0.0, 1.0)
    return fog


def compute_costs(
    rain_rate: np.ndarray,
    snow_depth: np.ndarray,
    fog_prob: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    UGV 기동비용 / 탐지비용 / 종합비용 산출 (모두 0~1 범위).

    mobility_cost: 강수·적설이 주요 요인 (지면 이동 방해)
    sensor_cost:   안개·강수가 주요 요인 (광학·레이더 센서 성능 저하)
    total_cost:    mobility 60% + sensor 40% 가중 합산
    """
    mob = rain_rate * 0.3 + snow_depth * 10.0 + fog_prob * 0.2
    sen = fog_prob * 0.6 + rain_rate * 0.1 + snow_depth * 0.05
    mob = np.clip(mob, 0.0, 1.0)
    sen = np.clip(sen, 0.0, 1.0)
    total = mob * 0.6 + sen * 0.4
    return mob, sen, total


# ──────────────────────────────────────────────
# grid_cells ↔ ERA5 격자 매핑
# ──────────────────────────────────────────────

def build_era5_kdtree(
    era5_lats: np.ndarray, era5_lons: np.ndarray
) -> tuple[cKDTree, np.ndarray]:
    """
    ERA5 격자점 전체를 KD-Tree로 구성.
    반환: (tree, coords_2d)  coords_2d shape = (N, 2)
    """
    lat_grid, lon_grid = np.meshgrid(era5_lats, era5_lons, indexing="ij")
    coords = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])
    tree = cKDTree(coords)
    return tree, coords


def map_grid_to_era5(
    grid_lats: np.ndarray,
    grid_lons: np.ndarray,
    era5_lats: np.ndarray,
    era5_lons: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    각 grid_cell의 (lat, lon) → 가장 가까운 ERA5 격자의 (lat_idx, lon_idx) 반환.
    """
    tree, _ = build_era5_kdtree(era5_lats, era5_lons)
    query_pts = np.column_stack([grid_lats, grid_lons])
    _, flat_idx = tree.query(query_pts)

    n_lon = len(era5_lons)
    lat_idx = flat_idx // n_lon
    lon_idx = flat_idx % n_lon
    return lat_idx, lon_idx


# ──────────────────────────────────────────────
# 레코드 생성 및 DB 삽입
# ──────────────────────────────────────────────

def build_records(
    ds: xr.Dataset,
    grid_df: pd.DataFrame,
    lat_idx: np.ndarray,
    lon_idx: np.ndarray,
    scenario_id: str,
) -> list[tuple]:
    """
    시간 스텝별로 순회하며 weather_forecasts INSERT용 튜플 생성.

    반환 컬럼 순서:
        scenario_id, grid_id, time_step,
        rain_rate, snow_depth, fog_prob,
        mobility_cost, sensor_cost, total_cost
    """
    var_tp  = _find_var(ds, "tp")
    var_sd  = _find_var(ds, "sd")
    var_t2m = _find_var(ds, "t2m")
    var_d2m = _find_var(ds, "d2m")

    missing = [k for k, v in {"tp": var_tp, "sd": var_sd, "t2m": var_t2m, "d2m": var_d2m}.items() if v is None]
    if missing:
        sys.exit(f"[ERROR] NetCDF에서 다음 변수를 찾을 수 없습니다: {missing}\n"
                 f"  사용 가능한 변수: {list(ds.data_vars)}")

    time_steps = ds["time"].values
    n_time = len(time_steps)
    n_grid = len(grid_df)

    records = []

    for t_idx, t_val in enumerate(time_steps):
        print(f"[INFO] 시간 스텝 처리 중: {t_idx + 1}/{n_time}", end="\r")

        # ERA5 변수값 추출 (2D 배열: lat × lon)
        tp_2d  = ds[var_tp].isel(time=t_idx).values   # m/hr (단위 주의: 일부 ERA5는 m/hr 누적)
        sd_2d  = ds[var_sd].isel(time=t_idx).values   # m
        t2m_2d = ds[var_t2m].isel(time=t_idx).values  # K
        d2m_2d = ds[var_d2m].isel(time=t_idx).values  # K

        # 각 grid_cell에 해당하는 ERA5 값 추출
        tp_vals  = tp_2d[lat_idx, lon_idx]
        sd_vals  = sd_2d[lat_idx, lon_idx]
        t2m_vals = t2m_2d[lat_idx, lon_idx]
        d2m_vals = d2m_2d[lat_idx, lon_idx]

        # 단위 변환: tp m → mm/hr (ERA5-Land tp는 시간 누적 강수량 m)
        rain_rate = np.clip(tp_vals * 1000.0, 0.0, None)  # m → mm
        snow_depth = np.clip(sd_vals, 0.0, None)

        # 안개 확률 산출
        fog_prob = compute_fog_prob(t2m_vals, d2m_vals)

        # 비용 산출
        mob_cost, sen_cost, tot_cost = compute_costs(rain_rate, snow_depth, fog_prob)

        # time_step: ISO 문자열로 저장
        time_step_str = str(pd.Timestamp(t_val).isoformat())

        for i in range(n_grid):
            records.append((
                scenario_id,
                str(grid_df.iloc[i]["cell_id"]),
                time_step_str,
                float(rain_rate[i]),
                float(snow_depth[i]),
                float(fog_prob[i]),
                float(mob_cost[i]),
                float(sen_cost[i]),
                float(tot_cost[i]),
            ))

    print(f"\n[INFO] 총 레코드 수: {len(records):,}  ({n_time} 스텝 × {n_grid:,} 셀)")
    return records


def insert_weather_forecasts(
    conn, records: list[tuple], batch_size: int = 5000
) -> None:
    """
    psycopg2 execute_values로 weather_forecasts 테이블에 bulk insert.
    (scenario_id, grid_id, time_step) 중복 시 비용 값 갱신 (UPSERT).
    """
    sql = """
        INSERT INTO weather_forecasts
            (scenario_id, grid_id, time_step,
             rain_rate, snow_depth, fog_prob,
             mobility_cost, sensor_cost, total_cost)
        VALUES %s
        ON CONFLICT (scenario_id, grid_id, time_step)
        DO UPDATE SET
            rain_rate     = EXCLUDED.rain_rate,
            snow_depth    = EXCLUDED.snow_depth,
            fog_prob      = EXCLUDED.fog_prob,
            mobility_cost = EXCLUDED.mobility_cost,
            sensor_cost   = EXCLUDED.sensor_cost,
            total_cost    = EXCLUDED.total_cost
    """
    total = len(records)
    inserted = 0

    with conn.cursor() as cur:
        for start in range(0, total, batch_size):
            batch = records[start : start + batch_size]
            execute_values(cur, sql, batch, page_size=batch_size)
            inserted += len(batch)
            print(f"[INFO] DB 삽입 진행: {inserted:,}/{total:,}", end="\r")

    conn.commit()
    print(f"\n[INFO] 전체 {total:,}행 삽입 완료")


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ERA5-Land NetCDF를 weather_forecasts 테이블에 적재합니다."
    )
    parser.add_argument("--scenario-id", required=True,
                        help="scenarios 테이블에 존재하는 scenario_id")
    parser.add_argument("--nc-file", required=True,
                        help="ERA5-Land NetCDF 파일 경로 (.nc)")
    parser.add_argument("--parquet-file", required=True,
                        help="grid_cells 위/경도 참조용 parquet 파일 경로")
    parser.add_argument("--batch-size", type=int, default=5000,
                        help="한 번에 삽입할 행 수 (기본값: 5000)")
    args = parser.parse_args()

    db_url = get_db_url()

    # ── 1. 데이터 로드 ──────────────────────────
    ds = load_netcdf(args.nc_file)
    era5_lats, era5_lons = extract_era5_coords(ds)

    parquet_path = Path(args.parquet_file)
    if not parquet_path.exists():
        sys.exit(f"[ERROR] parquet 파일을 찾을 수 없습니다: {parquet_path}")
    print(f"[INFO] parquet 로드 중: {parquet_path}")
    grid_df = pd.read_parquet(parquet_path, columns=["cell_id", "lat", "lon"])
    print(f"[INFO] grid_cells 수: {len(grid_df):,}")

    # ── 2. 격자 매핑 (KD-Tree) ─────────────────
    print("[INFO] ERA5 격자 매핑 중 (KD-Tree)...")
    lat_idx, lon_idx = map_grid_to_era5(
        grid_df["lat"].values,
        grid_df["lon"].values,
        era5_lats,
        era5_lons,
    )

    # ── 3. 레코드 생성 ──────────────────────────
    records = build_records(ds, grid_df, lat_idx, lon_idx, args.scenario_id)
    ds.close()

    # ── 4. DB 연결 및 삽입 ──────────────────────
    print("[INFO] DB 연결 중...")
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
                    f"[ERROR] scenario_id '{args.scenario_id}'가 scenarios 테이블에 없습니다."
                )

        # grid_cells가 먼저 적재됐는지 확인
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM grid_cells WHERE scenario_id = %s",
                (args.scenario_id,),
            )
            count = cur.fetchone()[0]
            if count == 0:
                sys.exit(
                    f"[ERROR] scenario_id '{args.scenario_id}'의 grid_cells 데이터가 없습니다. "
                    "먼저 load_grid.py를 실행하세요."
                )
            print(f"[INFO] grid_cells 확인: {count:,}행")

        insert_weather_forecasts(conn, records, batch_size=args.batch_size)

    finally:
        conn.close()

    print("[INFO] 완료.")


if __name__ == "__main__":
    main()
