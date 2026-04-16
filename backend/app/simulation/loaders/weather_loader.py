"""
backend/app/simulation/loaders/weather_loader.py

기상 예측 데이터 로드 (T/T+1/T+2/T+3 슬롯).
파일 경로 목록을 받아 각 타임슬롯 데이터를 반환.
"""

from pathlib import Path
from typing import Any


def load_weather(file_paths: dict[str, str]) -> dict[str, Any]:
    """
    file_paths: {"T0": "path/to/t0.parquet", "T1": ..., "T2": ..., "T3": ...}
    반환: {"T0": DataFrame, "T1": ..., ...}
    """
    import pandas as pd

    result: dict[str, Any] = {}
    for slot, path_str in file_paths.items():
        path = Path(path_str)
        if path.exists():
            result[slot] = pd.read_parquet(path)
        else:
            result[slot] = None
    return result
