"""
backend/app/simulation/loaders/safe_area_loader.py

safe_area_mask_triangle_FULL_20km_200m.tif → safe area 마스크 로드.
안전 구역: 1, 그 외: 0
"""

from pathlib import Path
from typing import Any


def load_safe_area(file_path: str) -> Any:
    """
    GeoTIFF 파일에서 safe area 마스크 로드.
    rasterio가 설치된 경우 numpy array 반환.
    없는 경우 file_path 문자열 반환 (참조용).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"safe area 파일 없음: {path}")

    try:
        import rasterio
        with rasterio.open(path) as src:
            return src.read(1)  # 첫 번째 밴드
    except ImportError:
        # rasterio 미설치 시 경로만 반환
        return str(path)
