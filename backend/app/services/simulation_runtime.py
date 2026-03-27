from __future__ import annotations

import asyncio
import contextlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.schemas.simulation_schema import SimulationStartRequest


UNIT_COLORS = {
    "1제대": "#dc2626",
    "2제대": "#16a34a",
    "3제대": "#2563eb",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clone_grid(rows: int, cols: int, fill: int = 0) -> list[list[int]]:
    return [[fill for _ in range(cols)] for _ in range(rows)]


def generate_terrain_grid(rows: int, cols: int) -> list[list[int]]:
    grid = _clone_grid(rows, cols)
    for r in range(rows):
        for c in range(cols):
            if 2 <= r <= min(4, rows - 1) and 4 <= c <= min(6, cols - 1):
                grid[r][c] = 1
            if 6 <= r <= min(8, rows - 1) and 8 <= c <= min(11, cols - 1):
                grid[r][c] = 2
            if r == min(9, rows - 1) and 2 <= c <= min(5, cols - 1):
                grid[r][c] = 1
            if c == min(13, cols - 1) and 3 <= r <= min(9, rows - 1):
                grid[r][c] = 2
            if (r in (1, 5, min(10, rows - 1)) and 1 <= c <= min(12, cols - 1)) or (
                c in (3, 9) and 1 <= r <= min(10, rows - 1)
            ):
                grid[r][c] = 3
    return grid


def generate_layer_grids(rows: int, cols: int) -> dict[str, list[list[int]]]:
    rain = _clone_grid(rows, cols)
    visibility = _clone_grid(rows, cols)
    soil = _clone_grid(rows, cols)
    risk = _clone_grid(rows, cols)
    for r in range(rows):
        for c in range(cols):
            if 2 <= r <= min(4, rows - 1) and 4 <= c <= min(6, cols - 1):
                rain[r][c] = 1
            if 6 <= r <= min(8, rows - 1) and 8 <= c <= min(11, cols - 1):
                risk[r][c] = 2
            if r == min(9, rows - 1) and 2 <= c <= min(5, cols - 1):
                soil[r][c] = 1
            if c == min(13, cols - 1) and 3 <= r <= min(9, rows - 1):
                visibility[r][c] = 2
            if 1 <= r <= min(3, rows - 1) and 10 <= c <= min(13, cols - 1):
                rain[r][c] = max(rain[r][c], 2)
            if 4 <= r <= min(7, rows - 1) and 7 <= c <= min(10, cols - 1):
                visibility[r][c] = max(visibility[r][c], 1)
            if 7 <= r <= min(10, rows - 1) and 1 <= c <= min(4, cols - 1):
                soil[r][c] = max(soil[r][c], 2)
            if (3 <= r <= min(6, rows - 1) and 5 <= c <= min(7, cols - 1)) or (
                7 <= r <= min(9, rows - 1) and 11 <= c <= min(13, cols - 1)
            ):
                risk[r][c] = max(risk[r][c], 1)
    return {"rain": rain, "visibility": visibility, "soil": soil, "risk": risk}


def build_unit_paths(rows: int, cols: int) -> dict[str, list[tuple[int, int]]]:
    last_r = rows - 1
    last_c = cols - 1
    return {
        "1제대": [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (4, 4), (5, 4), (6, 4)],
        "2제대": [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 3), (6, 4), (7, 5), (8, 6)],
        "3제대": [(0, 0), (1, 0), (2, 1), (3, 2), (4, 3), (5, 4), (6, 6), (7, 8), (7, 10), (7, 12), (min(9,last_r), min(14,last_c)), (last_r, last_c)],
    }


def make_units(rows: int, cols: int, ugv_count: int) -> list[dict[str, Any]]:
    paths = build_unit_paths(rows, cols)
    base_units = [
        {
            "id": "1제대",
            "name": "1제대",
            "color": UNIT_COLORS["1제대"],
            "identity": "RED",
            "start": "★ AOI-START",
            "end": "△ 1차 정찰지점",
            "ltwr": "RED",
            "sos": True,
            "summary": "강수·토양수분 영향으로 고위험 경로 진입 중",
            "path": paths["1제대"],
            "top3": [{"name": "강수", "value": 65}, {"name": "토양수분", "value": 45}, {"name": "지형", "value": 43}],
            "sos_detail": {"asset": "UGV-2", "rain": "8.4 mm/h", "visibility": "420 m", "soil": "0.31 m³/m³", "terrain": "비포장 저지대", "risk": "RED / 즉시 개입 권고", "note": "저시정과 진창화가 동시에 발생해 자율주행 유지가 불안정합니다."},
        },
        {
            "id": "2제대",
            "name": "2제대",
            "color": UNIT_COLORS["2제대"],
            "identity": "GREEN",
            "start": "★ AOI-START",
            "end": "□ 우회 회랑",
            "ltwr": "AMBER",
            "sos": False,
            "summary": "주의 단계 유지, 우회 경로 선택 시 안전여유 확보",
            "path": paths["2제대"],
            "top3": [{"name": "시정", "value": 52}, {"name": "강수", "value": 38}, {"name": "통신손실", "value": 27}],
            "sos_detail": {"asset": "이상 없음", "rain": "3.1 mm/h", "visibility": "890 m", "soil": "0.19 m³/m³", "terrain": "혼합 도로망", "risk": "AMBER / 관찰 필요", "note": "현재 SOS 신호는 없으나, 시정 저하가 진행 중이라 우회 유지가 권고됩니다."},
        },
        {
            "id": "3제대",
            "name": "3제대",
            "color": UNIT_COLORS["3제대"],
            "identity": "BLUE",
            "start": "★ AOI-START",
            "end": "◇ AOI-END",
            "ltwr": "RED",
            "sos": True,
            "summary": "센서 취약 셀 통과 중이며 SOS 가능성이 가장 높음",
            "path": paths["3제대"],
            "top3": [{"name": "강수", "value": 58}, {"name": "시정", "value": 51}, {"name": "위험도", "value": 47}],
            "sos_detail": {"asset": "UGV-6", "rain": "10.2 mm/h", "visibility": "280 m", "soil": "0.28 m³/m³", "terrain": "도심 외곽 협로", "risk": "RED / 대기열 우선 처리 대상", "note": "강수와 저시정으로 센서 블랙아웃 확률이 커져 통제관 개입이 필요합니다."},
        },
    ]
    # distribute ugvs dynamically
    ugv_names = [f"UGV-{i}" for i in range(1, ugv_count + 1)]
    idx = 0
    for unit in base_units:
        path = unit["path"]
        unit_ugvs = []
        for offset in (min(4, len(path)-1), min(8, len(path)-1)):
            if idx >= len(ugv_names):
                break
            unit_ugvs.append({"name": ugv_names[idx], "pos": path[offset], "path_index": offset})
            idx += 1
        unit["ugvs"] = unit_ugvs
    while idx < len(ugv_names):
        unit = base_units[idx % len(base_units)]
        unit["ugvs"].append({"name": ugv_names[idx], "pos": unit["path"][0], "path_index": 0})
        idx += 1
    return base_units


def _queue_schedule(units: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for unit in units:
        if unit["sos"] and unit["ugvs"]:
            rows.append({
                "unit": unit["name"],
                "asset": unit["ugvs"][-1]["name"],
                "wait": f"대기 {random.randint(1, 5)}분",
                "priority": "즉시 구조 필요" if unit["ltwr"] == "RED" else "관찰 필요",
            })
    return rows[:3]


def _mission_time_rows(units: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for idx, unit in enumerate(units, start=1):
        rows.append({
            "unit": unit["name"],
            "ugv": f"U{idx}: {unit['ugvs'][0]['name'] if unit['ugvs'] else 'N/A'}",
            "manned": f"M{idx}: 유인기",
            "remaining": f"{max(6, 26 - idx * 4)}분",
        })
    return rows


@dataclass
class SimulationRun:
    run_id: str
    config: SimulationStartRequest
    rows: int
    cols: int
    terrain_grid: list[list[int]]
    rain_grid: list[list[int]]
    visibility_grid: list[list[int]]
    soil_grid: list[list[int]]
    risk_grid: list[list[int]]
    units_data: list[dict[str, Any]]
    current_step: int = 0
    status: str = "running"
    mission_success_rate: int = 78
    estimated_cost: int = 1320
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    step_interval_sec: float = 1.0
    listeners: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None

    def build_snapshot(self) -> dict[str, Any]:
        queue = _queue_schedule(self.units_data)
        selected_path = self.units_data[-1]["path"] if self.units_data else []
        status_label = {"running": "진행중", "paused": "일시정지", "stopped": "종료"}.get(self.status, self.status)
        return {
            "run_id": self.run_id,
            "status": self.status,
            "current_step": self.current_step,
            "rows": self.rows,
            "cols": self.cols,
            "terrain_grid": self.terrain_grid,
            "rain_grid": self.rain_grid,
            "visibility_grid": self.visibility_grid,
            "soil_grid": self.soil_grid,
            "risk_grid": self.risk_grid,
            "units_data": self.units_data,
            "warning_cards": [
                {"priority": idx + 1, "title": unit["name"], "content": unit["summary"]}
                for idx, unit in enumerate(self.units_data)
            ],
            "planned_path": selected_path,
            "start_point": [0, 0],
            "end_point": [self.rows - 1, self.cols - 1],
            "ugv_positions": [ugv["pos"] for unit in self.units_data for ugv in unit["ugvs"]],
            "current_route_label": f"현재경로 A-01 / step {self.current_step}",
            "mission_status": status_label,
            "mission_success_rate": self.mission_success_rate,
            "estimated_cost": self.estimated_cost,
            "alternative_route": {
                "name": "차선책 경로 B-02",
                "success_rate": max(40, self.mission_success_rate - 6),
                "cost": max(900, self.estimated_cost - 120),
                "reason": "고위험 셀을 우회하며 대기열 붕괴 위험을 낮추는 대안입니다.",
            },
            "mission_time_rows": _mission_time_rows(self.units_data),
            "queue_schedule": queue,
            "report_data": [
                {"time": f"T+{max(0,self.current_step-2)}", "risk": "Amber", "queue_length": max(1, len(queue)), "reroute": False},
                {"time": f"T+{max(0,self.current_step-1)}", "risk": "Red" if len(queue) >= 2 else "Amber", "queue_length": len(queue), "reroute": len(queue) >= 2},
                {"time": f"T+{self.current_step}", "risk": "Red" if any(u['ltwr']=='RED' for u in self.units_data) else "Amber", "queue_length": len(queue), "reroute": True},
            ],
            "updated_at": self.updated_at,
        }

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for listener in self.listeners:
            try:
                listener.put_nowait({"event": event, **payload})
            except asyncio.QueueFull:
                dead.append(listener)
        for q in dead:
            self.listeners.discard(q)

    async def tick(self) -> None:
        if self.status != "running":
            return
        self.current_step += 1
        self.updated_at = utc_now_iso()
        # simple dynamics
        for unit in self.units_data:
            for ugv in unit["ugvs"]:
                next_index = min(ugv["path_index"] + 1, len(unit["path"]) - 1)
                ugv["path_index"] = next_index
                ugv["pos"] = unit["path"][next_index]
            if self.current_step % 3 == 0:
                unit["ltwr"] = random.choice(["AMBER", "RED"])
                unit["sos"] = unit["ltwr"] == "RED"
        self.mission_success_rate = max(45, min(96, self.mission_success_rate + random.choice([-2, -1, 0, 1])))
        self.estimated_cost += random.choice([10, 20, 30])
        await self.broadcast("simulation_tick", {"snapshot": self.build_snapshot()})
        if self.current_step % 4 == 0:
            unit = random.choice(self.units_data)
            await self.broadcast(
                "alert_created",
                {
                    "run_id": self.run_id,
                    "alert": {
                        "unit": unit["name"],
                        "message": f"{unit['name']} 경로 재평가 필요 (step {self.current_step})",
                        "level": unit["ltwr"],
                    },
                },
            )


class SimulationManager:
    def __init__(self) -> None:
        self.runs: dict[str, SimulationRun] = {}

    async def create_run(self, config: SimulationStartRequest) -> SimulationRun:
        run_id = uuid.uuid4().hex[:12]
        layers = generate_layer_grids(config.rows, config.cols)
        run = SimulationRun(
            run_id=run_id,
            config=config,
            rows=config.rows,
            cols=config.cols,
            terrain_grid=generate_terrain_grid(config.rows, config.cols),
            rain_grid=layers["rain"],
            visibility_grid=layers["visibility"],
            soil_grid=layers["soil"],
            risk_grid=layers["risk"],
            units_data=make_units(config.rows, config.cols, config.ugv_count),
            step_interval_sec=config.step_interval_sec,
        )
        run.task = asyncio.create_task(self._runner(run))
        self.runs[run_id] = run
        return run

    async def _runner(self, run: SimulationRun) -> None:
        try:
            while run.status != "stopped":
                await asyncio.sleep(run.step_interval_sec)
                await run.tick()
        except asyncio.CancelledError:
            pass

    def get_run(self, run_id: str) -> SimulationRun | None:
        return self.runs.get(run_id)

    async def command(self, run_id: str, action: str) -> SimulationRun:
        run = self.runs[run_id]
        if action == "pause":
            run.status = "paused"
        elif action == "resume":
            run.status = "running"
        elif action == "stop":
            run.status = "stopped"
            if run.task:
                run.task.cancel()
        elif action == "tick":
            await run.tick()
        run.updated_at = utc_now_iso()
        await run.broadcast("simulation_state_changed", {"snapshot": run.build_snapshot()})
        return run

    async def add_listener(self, run_id: str) -> asyncio.Queue:
        run = self.runs[run_id]
        q: asyncio.Queue = asyncio.Queue(maxsize=20)
        run.listeners.add(q)
        await q.put({"event": "simulation_snapshot", "snapshot": run.build_snapshot()})
        return q

    def remove_listener(self, run_id: str, q: asyncio.Queue) -> None:
        run = self.runs.get(run_id)
        if run:
            run.listeners.discard(q)

    async def shutdown(self) -> None:
        for run in self.runs.values():
            if run.task:
                run.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run.task


simulation_manager = SimulationManager()
