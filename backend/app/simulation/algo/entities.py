import numpy as np

class BaseAgent:
    """모든 에이전트의 공통 속성"""
    def __init__(self, agent_id, start_pos):
        self.agent_id = agent_id
        self.pos = np.array(start_pos, dtype=float) # (y, x)
        self.ap = 1000000  # 첫 턴 시작용
        self.history = []

    def start_new_turn(self):
        """[사용자 요청 반영] 턴 시작 시 100만 AP를 누적 추가"""
        self.ap += 1000000

class UGV(BaseAgent):
    def __init__(self, agent_id, start_pos, target_pos, config):
        super().__init__(agent_id, start_pos)
        self.final_target = np.array(target_pos)
        self.config = config  # 이제 self.config를 사용할 수 있습니다!
        self.mode = "MISSION"
        self.path_queue = []   # 다익스트라가 계산해준 경로 (Waypoint 리스트)
        self.last_model_time = None # 마지막으로 경로를 계산했을 때의 예보 모델 시각

    def decide_and_act(self, env, comm_mask, pathfinder):
            """
            [수정] 10분마다 무조건 최적 경로를 다시 계산합니다.
            """
            # 1. 현재 위치 기반 통신 모드 결정 (Hysteresis)
            y, x = int(self.pos[0]), int(self.pos[1])
            zone_value = comm_mask[y, x]
            if zone_value == 0:   self.mode = "RECALL"
            elif zone_value == 2: self.mode = "MISSION"

            # 2. 목적지 설정
            current_target = self.final_target if self.mode == "MISSION" else env.manned_pos

            # 3. [10분 주기 강제 계산] 현재 가용한 가장 최신 기상 큐브로 다익스트라 실행
            # env.get_active_time_cube()는 항상 T=0에 실제 기상을 담고 있음
            self.path_queue = pathfinder.solve(self.pos, current_target, env)

            # 4. 실제 이동 (계산된 경로의 첫 번째 칸으로 이동)
            if len(self.path_queue) > 1:
                next_pos = np.array(self.path_queue[1]) # 0번은 현재 위치이므로 1번으로 이동
                
                # 비용 계산 및 AP 차감
                step_cost = self.calculate_step_cost(self.pos, next_pos, env)
                self.ap -= step_cost
                
                # 위치 업데이트 및 기록
                self.pos = next_pos
                self.history.append((env.sim_time, self.pos.copy(), self.mode, self.ap))
                
                # 6. 수색 도장 찍기 (엔진의 coverage_map에 반영)
                # env.update_coverage(self.pos, self.current_speed, env.current_visibility)

    def calculate_step_cost(self, start, end, env):
        """
        한 칸 이동 시 발생하는 시공간 복합 비용 계산
        """
        # 대각선 이동 여부 판정 (1.414배 적용)
        is_diagonal = np.abs(start[0]-end[0]) + np.abs(start[1]-end[1]) == 2
        dist_factor = 1.414 if is_diagonal else 1.0
        
        # 도착 예정 시각의 기상 데이터 레이어 인덱스 획득
        # (현재는 단순화하여 T=0 레이어 혹은 AP 소모량 기반 예측 인덱스 사용)
        target_layer_idx = env.get_layer_idx(env.sim_time) 
        
        # 지형 비용 + 기상(전술) 비용
        terrain_cost = env.base_layer[int(end[0]), int(end[1])]
        weather_cost = env.active_layers[target_layer_idx, int(end[0]), int(end[1])]
        
        # 최종 AP 소모량 (기본 가중치 10만 등을 곱해 스케일 조정)
        return (terrain_cost * dist_factor + weather_cost) * self.config.AP_UNIT_COST

class MannedVehicle(BaseAgent):
    def decide_and_act(self, env, ugvs):
        """
        유인기의 매 액션(Action)마다 실행되는 로직
        """
        # 1. 비상 상태 체크: 어떤 UGV라도 RECALL 모드인지 확인
        is_emergency = any(u.mode == "RECALL" for u in ugvs)
        
        if is_emergency:
            # 비상 상황 발생 시 즉시 추종 중단 및 정지
            self.history.append((env.sim_time, self.pos.copy(), "EMERGENCY_STOP", self.ap))
            # 유인기가 정지해 있어야 UGV들이 안정적으로 복귀할 수 있습니다.
            return

        # 2. 실시간 무게중심(CoM) 계산
        # (무인기들이 이동 중일 수 있으므로, 호출 시점의 최신 위치를 사용합니다)
        ugv_positions = [u.pos for u in ugvs]
        com = np.mean(ugv_positions, axis=0)
        
        # 3. 정지 조건 확인: CoM과 1km(5셀) 이내면 정지
        dist_to_com = np.linalg.norm(self.pos - com)
        if dist_to_com <= 5.0:
            self.history.append((env.sim_time, self.pos.copy(), "STATIONARY", self.ap))
            return

        # 4. 이동 수행: CoM 방향으로 지형 비용만 고려하여 1칸 이동
        next_pos = self._get_best_step_towards(com, env)
        
        # 이동 비용 차감 (지형 비용만 반영)
        step_cost = self.calculate_step_cost(self.pos, next_pos, env)
        self.ap -= step_cost
        
        self.pos = next_pos
        self.history.append((env.sim_time, self.pos.copy(), "FOLLOWING", self.ap))
        
        # [중요] 이동 후 즉시 환경의 통신 마스크를 업데이트합니다.
        env.update_comm_mask(self.pos)

    def _get_best_step_towards(self, target, env):
        """CoM 방향 8방향 중 지형 비용을 고려한 최적 칸 반환"""
        moves = [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]
        best_pos = self.pos
        min_score = float('inf')

        for dy, dx in moves:
            ny, nx = int(self.pos[0] + dy), int(self.pos[1] + dx)
            
            # 맵 경계 및 이동 불가능 지형(Built-up, Water 등) 체크
            if 0 <= ny < env.ny and 0 <= nx < env.nx:
                terrain_cost = env.base_layer[ny, nx]
                if terrain_cost > 100: # 이동 불가 지형은 제외
                    continue
                
                new_pos = np.array([ny, nx])
                dist = np.linalg.norm(new_pos - target)
                
                # 점수 = 타겟까지의 거리 + 지형 가중치 (기상 배제)
                score = dist + (terrain_cost * 0.1) 
                
                if score < min_score:
                    min_score = score
                    best_pos = new_pos
        return best_pos

    def calculate_step_cost(self, start, end, env):
        """유인기 전용 비용 계산 (기상/사고 확률 배제)"""
        is_diagonal = np.sum(np.abs(start - end)) == 2
        dist_factor = 1.414 if is_diagonal else 1.0
        
        # env.active_layers(기상)를 참조하지 않고 오직 base_layer(지형)만 참조
        terrain_cost = env.base_layer[int(end[0]), int(end[1])]
        return terrain_cost * dist_factor * self.config.AP_UNIT_COST

class Controller(BaseAgent):
    """통제관: 시간 동기화 및 수리/재인가 관리"""
    def __init__(self, agent_id):
        super().__init__(agent_id, [0, 0])

    def sync_time(self, max_agent_ap):
        """아무 이벤트가 없을 때, 세트 내 최고 AP 소유자와 시간을 맞춤"""
        if self.ap > max_agent_ap: # 내가 더 앞서 있다면 (할 일 없음)
             self.ap = max_agent_ap