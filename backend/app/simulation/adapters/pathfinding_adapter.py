"""
backend/app/simulation/adapters/pathfinding_adapter.py

경로 탐색 어댑터.

인터페이스:
    입력: base(출발지), targets(목적지 목록), risk_layers, route_policy
    출력: PathfindingResult (initial_routes, updated_routes, reroute_reasons)

현재는 더미 구현 (직선 경로 반환).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteResult:
    unit_no: int
    route_type: str  # INITIAL | UPDATED
    geojson: dict
    reason: str | None = None


@dataclass
class PathfindingResult:
    initial_routes: list[RouteResult] = field(default_factory=list)
    updated_routes: list[RouteResult] = field(default_factory=list)
    reroute_reasons: list[str] = field(default_factory=list)


def find_paths(
    base: dict,
    targets: list[dict],
    risk_layers: dict[str, Any],
    route_policy: dict | None = None,
    ugv_count: int = 1,
) -> PathfindingResult:
    """
    경로 탐색.
    현재: 출발지→목적지 직선 더미 경로 반환.
    """
    routes = []
    for i in range(ugv_count):
        target = targets[i % len(targets)] if targets else base
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [base.get("lon", 0), base.get("lat", 0)],
                    [target.get("lon", 0), target.get("lat", 0)],
                ],
            },
            "properties": {"unit_no": i + 1},
        }
        routes.append(RouteResult(unit_no=i + 1, route_type="INITIAL", geojson=geojson))

    return PathfindingResult(initial_routes=routes)
