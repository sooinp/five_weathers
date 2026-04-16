"""
backend/app/simulation/algo/sim_config.py

mumt_sim 알고리즘에 필요한 설정값 모음.
백엔드 서버 설정(config.py)과 분리된 알고리즘 전용 설정.
"""

import os

# backend/ 루트 기준 절대 경로
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)))


class SimAlgoConfig:
    """mumt_sim Environment / PathFinder3D / SimulationEngine 에 전달되는 설정 객체."""

    # ── 데이터 경로 ───────────────────────────────────────────────────────
    TERRAIN_PATH: str = os.path.join(
        _BASE, "data", "map", "static",
        "Test_sim_input_200m_bbox_2km.parquet"
    )
    DYNAMIC_DIR: str = os.path.join(_BASE, "data", "map", "dynamic")

    # ── 그리드 설정 ──────────────────────────────────────────────────────
    # 실제 parquet 파일: 10×10 = 100 rows (200m 해상도, 2km×2km)
    GRID_SIZE: tuple = (10, 10)

    # 시공간 그래프 타임 레이어 수 (10분 × 18 = 180분 예보)
    NT: int = 18

    # ── AP 설정 ──────────────────────────────────────────────────────────
    AP_UNIT_COST: float = 100_000.0  # 타일 비용 → AP 변환 계수

    # ── 좌표 변환 (grid row/col → WGS-84 lat/lon) ────────────────────────
    # 10×10 그리드, 셀 크기 200m, 좌상단(row=0, col=0) 기준점
    ORIGIN_LAT: float = 37.510   # row=0 중심 위도
    ORIGIN_LON: float = 127.000  # col=0 중심 경도
    CELL_LAT: float = 0.00180    # 200m ≈ 0.00180° 위도
    CELL_LON: float = 0.00228    # 200m / cos(37.5°) ≈ 0.00228° 경도

    @classmethod
    def grid_to_latlon(cls, row: float, col: float) -> tuple[float, float]:
        """그리드 (row, col) → (lat, lon)"""
        lat = cls.ORIGIN_LAT + row * cls.CELL_LAT
        lon = cls.ORIGIN_LON + col * cls.CELL_LON
        return lat, lon

    @classmethod
    def latlon_to_grid(cls, lat: float, lon: float) -> tuple[int, int]:
        """(lat, lon) → 가장 가까운 그리드 (row, col)"""
        row = round((lat - cls.ORIGIN_LAT) / cls.CELL_LAT)
        col = round((lon - cls.ORIGIN_LON) / cls.CELL_LON)
        row = max(0, min(row, cls.GRID_SIZE[0] - 1))
        col = max(0, min(col, cls.GRID_SIZE[1] - 1))
        return row, col
