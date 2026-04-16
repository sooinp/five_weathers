"""
backend/app/utils/validators.py

입력값 검증 유틸리티.
"""


def validate_lat_lon(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def validate_ugv_count(count: int, max_count: int) -> bool:
    return 1 <= count <= max_count
