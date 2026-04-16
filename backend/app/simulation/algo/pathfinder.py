import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

class PathFinder3D:
    def __init__(self, grid_size, nt):
        self.ny, self.nx = grid_size
        self.nt = nt
        self.n_nodes_per_layer = self.ny * self.nx
        self.total_nodes = self.nt * self.n_nodes_per_layer
        
        # [최적화] 그래프의 뼈대(구조)를 미리 한 번만 파놓습니다.
        self._precompute_graph_structure()

    def _precompute_graph_structure(self):
        """이동 가능한 모든 간선의 (u, v) 좌표와 거리 가중치를 미리 계산"""
        t, y, x = np.meshgrid(np.arange(self.nt - 1), 
                              np.arange(self.ny), 
                              np.arange(self.nx), indexing='ij')
        
        u = self.get_node_idx(t, y, x)
        directions = [
            (0, 0, 0.5),   # 대기
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)
        ]

        all_u, all_v, all_dist, all_ny, all_nx, all_nt = [], [], [], [], [], []

        for dy, dx, dist in directions:
            ny, nx = y + dy, x + dx
            mask = (ny >= 0) & (ny < self.ny) & (nx >= 0) & (nx < self.nx)
            
            all_u.append(u[mask])
            all_v.append(self.get_node_idx(t[mask] + 1, ny[mask], nx[mask]))
            all_dist.append(np.full(np.sum(mask), dist))
            # 가중치 업데이트를 위해 타겟 좌표 저장
            all_ny.append(ny[mask])
            all_nx.append(nx[mask])
            all_nt.append(t[mask] + 1)

        self._u = np.concatenate(all_u)
        self._v = np.concatenate(all_v)
        self._dist_factor = np.concatenate(all_dist)
        self._target_ny = np.concatenate(all_ny)
        self._target_nx = np.concatenate(all_nx)
        self._target_nt = np.concatenate(all_nt)

    def get_node_idx(self, t, y, x):
        return t * self.n_nodes_per_layer + y * self.nx + x

    def solve(self, start_pos, end_pos, env):
        """
        [핵심] 10분마다 호출되는 메인 메서드
        1. 현재 기상에 맞춰 가중치만 광속 업데이트
        2. 다익스트라 실행
        3. 경로 복원
        """
        # 1. 가중치 계산 (지형 + 기상) * 거리 가중치
        # env.get_active_time_cube()로부터 최신 180분분 데이터를 가져옴
        time_cube = env.get_active_time_cube() 
        
        costs = (env.base_layer[self._target_ny, self._target_nx] + 
                 time_cube[self._target_nt, self._target_ny, self._target_nx]) * self._dist_factor
        
        # 2. CSR 행렬 생성 (구조는 고정, data만 새로 주입)
        graph = csr_matrix((costs, (self._u, self._v)), shape=(self.total_nodes, self.total_nodes))
        
        # 3. 다익스트라 실행 (T=0 지점의 시작 위치에서 출발)
        start_node_idx = self.get_node_idx(0, int(start_pos[0]), int(start_pos[1]))
        dist_matrix, predecessors = dijkstra(csgraph=graph, directed=True, 
                                            indices=start_node_idx, return_predecessors=True)
        
        # 4. 목적지 도달 시점 중 최소 비용 시점 찾기 및 경로 복원
        return self.find_path(dist_matrix, predecessors, (0, int(start_pos[0]), int(start_pos[1])), end_pos)

    def find_path(self, dist_matrix, predecessors, start_coord, end_pos):
        """기존 코드와 동일하되, 경로가 없을 경우의 예외처리 강화"""
        start_node = self.get_node_idx(*start_coord)
        
        # 목적지(end_pos)의 모든 시간 레이어 중 최소값 탐색
        target_nodes = [self.get_node_idx(t, int(end_pos[0]), int(end_pos[1])) for t in range(self.nt)]
        best_node = target_nodes[np.argmin(dist_matrix[target_nodes])]
        
        if dist_matrix[best_node] == np.inf:
            return [] # 경로 없음

        path = []
        curr = best_node
        while curr != start_node:
            path.append(curr)
            curr = predecessors[curr]
            if curr < 0: break # 연결 끊김
        path.append(start_node)
        
        coords = []
        for idx in path[::-1]:
            t = idx // self.n_nodes_per_layer
            rem = idx % self.n_nodes_per_layer
            coords.append((rem // self.nx, rem % self.nx)) # (y, x)만 반환 (t는 내부용)
            
        return coords