"""
backend/app/simulation/loaders/static_grid_loader.py

sim_input_200m_bbox_50km.parquet → 정적 격자 데이터 로드.
orchestrator가 run 시작 시 호출.
"""

from pathlib import Path

import pandas as pd


def load_static_grid(file_path: str) -> pd.DataFrame:
    """
    parquet 파일에서 격자 데이터 로드.

    반환 컬럼:
        cell_id, lat, lon, lc_code, mask_good, roads_has_drivable_road
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"static grid 파일 없음: {path}")
    return pd.read_parquet(path)
