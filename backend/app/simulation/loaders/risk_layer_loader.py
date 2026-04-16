"""
backend/app/simulation/loaders/risk_layer_loader.py

위험도 레이어 파일 로드.
총 위험 맵 (T0~T3) + 10분 단위 보간 레이어 참조 경로 반환.
"""

from pathlib import Path


def load_risk_layer_paths(
    base_dir: str, time_slots: list[str] | None = None
) -> dict[str, str | None]:
    """
    base_dir에서 각 타임슬롯 위험도 맵 경로 탐색.

    반환:
        {"T0": "path/to/risk_T0.tif", "T1": ..., "T2": ..., "T3": ...}
        파일이 없으면 None.
    """
    if time_slots is None:
        time_slots = ["T0", "T1", "T2", "T3"]

    base = Path(base_dir)
    result: dict[str, str | None] = {}
    for slot in time_slots:
        candidates = list(base.glob(f"*risk*{slot}*.tif")) + list(
            base.glob(f"*{slot}*risk*.tif")
        )
        result[slot] = str(candidates[0]) if candidates else None
    return result
