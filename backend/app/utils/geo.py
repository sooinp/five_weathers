"""
backend/app/utils/geo.py

지리 좌표 관련 유틸리티.
"""

import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 간 거리 (km) 계산 — Haversine 공식."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def make_point_geojson(lat: float, lon: float, properties: dict | None = None) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties or {},
    }


def make_linestring_geojson(
    coords: list[tuple[float, float]], properties: dict | None = None
) -> dict:
    """coords: [(lat, lon), ...]"""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in coords],
        },
        "properties": properties or {},
    }
