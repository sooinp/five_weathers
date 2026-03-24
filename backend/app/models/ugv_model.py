## 🔥 'mesa 연습' 코드 여기 들어감

import mesa
import random
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from mesa.datacollection import DataCollector
import pandas as pd

# =========================
# 1. 에이전트
# =========================
class UGVAgent(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

        self.battery = 200
        self.destination = (model.grid.width - 1, model.grid.height - 1)

        try:
            self.planned_path = nx.shortest_path(
                self.model.graph,
                source=(0, 0),
                target=self.destination,
                weight='weight'
            )
            self.full_path = list(self.planned_path)
            self.planned_path.pop(0)

        except nx.NetworkXNoPath:
            self.planned_path = []
            self.full_path = []

    def step(self):
        if not self.planned_path:
            return

        current_pos = self.pos
        next_pos = self.planned_path.pop(0)
        self.model.grid.move_agent(self, next_pos)

        dx = abs(next_pos[0] - current_pos[0])
        dy = abs(next_pos[1] - current_pos[1])
        is_diagonal = (dx == 1 and dy == 1)

        base_battery = 14 if is_diagonal else 10

        weather = self.model.weather_map.get(next_pos, "Clear")
        actual_consume = base_battery * 2 if weather == "Severe" else base_battery

        self.battery -= actual_consume


# =========================
# 2. 모델
# =========================
class UGVModel(mesa.Model):
    def __init__(self, width, height):
        super().__init__()

        self.schedule = mesa.time.RandomActivation(self)

        self.grid = mesa.space.MultiGrid(width, height, torus=False)
        self.steps = 0

        # 좌표 생성
        all_coords = [(x, y) for x in range(width) for y in range(height)]
        all_coords.remove((0, 0))
        all_coords.remove((width - 1, height - 1))

        # 장애물
        self.obstacles = random.sample(all_coords, 20)
        for coord in self.obstacles:
            all_coords.remove(coord)

        # 날씨
        self.weather_map = {
            coord: "Severe" for coord in random.sample(all_coords, 20)
        }

        # 그래프 생성
        self.graph = nx.Graph()

        for x in range(width):
            for y in range(height):
                if (x, y) not in self.obstacles:
                    self.graph.add_node((x, y))

        for node in self.graph.nodes:
            x, y = node

            for dx, dy in [
                (0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1)
            ]:
                neighbor = (x + dx, y + dy)

                if neighbor in self.graph.nodes:

                    is_diagonal = (dx != 0 and dy != 0)
                    base_cost = 14 if is_diagonal else 10

                    if (
                        self.weather_map.get(node) == "Severe"
                        or self.weather_map.get(neighbor) == "Severe"
                    ):
                        cost = base_cost * 2
                    else:
                        cost = base_cost

                    self.graph.add_edge(node, neighbor, weight=cost)

        # 에이전트 생성
        ugv = UGVAgent(1, self)
        self.schedule.add(ugv)

        # DataCollector
        self.datacollector = DataCollector(
            agent_reporters={
                "X좌표": lambda a: a.pos[0] if a.pos else None,
                "Y좌표": lambda a: a.pos[1] if a.pos else None,
                "잔여배터리": "battery",
                "현재날씨": lambda a: a.model.weather_map.get(a.pos, "Clear") if a.pos else "Clear"
            }
        )

    def step(self):
        self.schedule.step()
        self.steps += 1
        self.datacollector.collect(self)


# =========================
# 3. 🔥 핵심: 외부 호출 함수
# =========================
def run_simulation(width=10, height=10, steps=15):
    model = UGVModel(width, height)

    for _ in range(steps):
        model.step()

    # 로그 데이터
    df = model.datacollector.get_agent_vars_dataframe()
    df = df.reset_index().rename(columns={
        "Step": "턴",
        "AgentID": "에이전트ID"
    })

    # grid 정보
    grid_data = {
        "obstacles": model.obstacles,
        "weather": model.weather_map,
        "destination": (width - 1, height - 1)
    }

    # 에이전트 정보
    agents = []
    for agent in model.agents:
        agents.append({
            "pos": agent.pos,
            "battery": agent.battery,
            "path": getattr(agent, "full_path", [])
        })

    return {
        "log": df.to_dict(orient="records"),
        "grid": grid_data,
        "agents": agents
    }