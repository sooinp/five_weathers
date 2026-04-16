import numpy as np
from datetime import timedelta

class SimulationEngine:
    def __init__(self, env, pathfinder, config):
        self.env = env
        self.pathfinder = pathfinder
        self.config = config
        self.agents = []
        self.manned_vehicle = None

    def add_agent(self, agent):
        # 유인기와 무인기를 구분하여 저장
        if hasattr(agent, 'is_manned') and agent.is_manned:
            self.manned_vehicle = agent
        else:
            self.agents.append(agent)

    def run_one_tick(self):
        """
        10분(1 틱) 동안의 시나리오: UGV 선행 -> 유인기 추종
        """
        # 1. 환경 및 AP 초기화
        self.env.get_active_time_cube()
        self._reset_all_ap()

        # 2. 무인기(UGV)들 먼저 행동 (Step-by-Step)
        # UGV들은 '이전 틱 마지막에 확정된 통신 마스크'를 보고 이동합니다.
        for agent in self.agents:
            self._process_agent_actions(agent)

        # 3. 유인기(Manned Vehicle) 행동
        # UGV들이 이동을 마친 '최신 좌표'를 기준으로 무게중심을 계산하여 이동합니다.
        if self.manned_vehicle:
            self._process_agent_actions(self.manned_vehicle)
            # 유인기가 이동을 마친 후 즉시 다음 틱을 위한 통신 마스크 갱신
            self.env.update_comm_mask(self.manned_vehicle.pos)

        # 4. 시간 경과 및 예보 업데이트
        self._advance_time()

    def _process_agent_actions(self, agent):
        """에이전트가 AP를 소모하며 행동하는 루프"""
        while agent.ap > 0:
            old_pos = agent.pos.copy()
            
            if hasattr(agent, 'is_manned') and agent.is_manned:
                # 유인기: 방금 이동을 마친 UGV들의 위치를 참조
                agent.decide_and_act(self.env, self.agents)
            else:
                # 무인기: 현재 환경의 통신 마스크를 참조
                agent.decide_and_act(self.env, self.env.comm_mask, self.pathfinder)
            
            # 이동하지 않았거나 AP가 부족하면 행동 종료
            if np.array_equal(old_pos, agent.pos) or agent.ap < 1000:
                break

    def _reset_all_ap(self):
        if self.manned_vehicle: self.manned_vehicle.ap = 1000000
        for agent in self.agents: agent.ap = 1000000

    def _advance_time(self):
        self.env.sim_time += timedelta(minutes=10)
        if self.env.sim_time.minute == 0:
            self.env.update_forecast_model(self.env.sim_time)